import asyncio
import websockets
import json
import time
from typing import Optional
from websockets.asyncio.client import ClientConnection
from websockets.asyncio.server import ServerConnection
from websockets.http11 import Request, Response
from websockets.typing import Data
from config import APP_SETTING
from utils import send_by_auth, logger, forward_message


ONEBOT_PROTOCOL_SIDE: Optional[ClientConnection] = None
"""OneBot 协议端WebSocket连接"""

LANG_SERVICE_SIDE_SET: set[ServerConnection] = set()
"""后端WebSocket服务器连接列表"""

DEAD_MSG_QUEUE: list[Data] = []
"""当协议端断开连接时，将消息存入此队列，等待重连后再发送"""

BOT_ID: int = 0
"""Bot ID"""


async def send_to_all_client(message: Data):
    """
    向客户端推送事件消息
    """
    global LANG_SERVICE_SIDE_SET, ECHO_DICT
    # 将要转发给客户端的消息
    data: dict = json.loads(str(message))
    expire_clients: set[ServerConnection] = set()
    # 如果有回声字段，则转发给对应的客户端
    if echo := data.get("echo"):
        client = ECHO_DICT.pop(echo)
        logger.info(f"echo: {echo}, callback: {message}")
        if client:
            # 尝试发送5次，如果失败则移除客户端连接
            for _ in range(5):
                if await forward_message(client, message):
                    break
            else:
                expire_clients.add(client)
    # 否则广播给所有客户端
    else:
        logger.info(f"broadcast, event: {message}")
        for client in LANG_SERVICE_SIDE_SET:
            # 尝试发送5次，如果失败则移除客户端连接
            for _ in range(5):
                if await forward_message(client, message):
                    break
            else:
                expire_clients.add(client)
    # 移除过期客户端连接
    for client in expire_clients:
        logger.warning(f"client {client.remote_address} expired, remove")
        await client.close()
        LANG_SERVICE_SIDE_SET.remove(client)


async def server_to_client():
    """
    将 onebot 协议端事件转发到 Bot 服务端
    """
    global ONEBOT_PROTOCOL_SIDE, BOT_ID, LAST_HEARTBEAT_TIME
    if not ONEBOT_PROTOCOL_SIDE:
        return
    try:
        async for message in ONEBOT_PROTOCOL_SIDE:
            # 处理黑白名单消息
            # 如果消息是从被转发的 ws 发送过来，则进行判断处理，否则直接放行
            data: dict = json.loads(str(message))
            # 白名单优先于黑名单
            gid = data.get("group_id")
            if gid:
                gid = int(str(gid))
                if send_by_auth(gid):
                    await send_to_all_client(message)
            else:
                if (
                    data.get("post_type") == "meta_event"
                    and data.get("meta_event_type") == "lifecycle"
                    and data.get("sub_type") == "connect"
                ):
                    # 连接成功通知事件，不处理
                    BOT_ID = int(str(data.get("self_id")))
                    LAST_HEARTBEAT_TIME = int(str(data.get("time")))
                    # 创建心跳检测任务
                    asyncio.create_task(alive_check())
                    continue
                if (
                    data.get("post_type") == "meta_event"
                    and data.get("meta_event_type") == "heartbeat"
                ):
                    # 心跳通知事件
                    LAST_HEARTBEAT_TIME = int(str(data.get("time")))

                await send_to_all_client(message)
    except:  # noqa: E722
        logger.warning(
            f"server {ONEBOT_PROTOCOL_SIDE.remote_address} closed, waiting for reconnect"
        )
        await reconnect_server()


ECHO_DICT: dict[str, ServerConnection] = {}


async def client_to_server(ws: ServerConnection):
    """
    将 Bot 服务端API调用转发到 onebot 协议端
    """
    global ONEBOT_PROTOCOL_SIDE, DEAD_MSG_QUEUE, ECHO_DICT
    if not ONEBOT_PROTOCOL_SIDE:
        return
    try:
        async for message in ws:
            # 转发消息到后端WebSocket服务器
            logger.info(f"invoke, api: {message}")
            data: dict = json.loads(str(message))
            gid = data.get("params", {}).get("group_id")
            if gid:
                gid = int(str(gid))
                if send_by_auth(gid):
                    for _ in range(5):
                        if await forward_message(ONEBOT_PROTOCOL_SIDE, message):
                            echo = str(data.get("echo"))
                            ECHO_DICT.update({echo: ws})
                            break
                    else:
                        DEAD_MSG_QUEUE.append(message)
                        # 超过重试次数，证ws连接已关闭
                        logger.warning(
                            f"server {ONEBOT_PROTOCOL_SIDE.remote_address} closed, waiting for reconnect"
                        )
                        await reconnect_server()
            else:
                for _ in range(5):
                    if await forward_message(ONEBOT_PROTOCOL_SIDE, message):
                        echo = str(data.get("echo"))
                        ECHO_DICT.update({echo: ws})
                        break
                else:
                    DEAD_MSG_QUEUE.append(message)
                    # 超过重试次数，证ws连接已关闭
                    logger.warning(
                        f"server {ONEBOT_PROTOCOL_SIDE.remote_address} closed, waiting for reconnect"
                    )
                    await reconnect_server()
    except:  # noqa: E722
        # 客户端连接断开，移除客户端连接
        logger.warning(f"client {ws.remote_address} closed, remove")
        LANG_SERVICE_SIDE_SET.remove(ws)


CONNECT_LIOK = asyncio.Lock()
"""异步锁，避免多次发出协议端重连请求"""


async def reconnect_server():
    """
    尝试重新连接后端WebSocket服务器
    """
    global ONEBOT_PROTOCOL_SIDE, APP_SETTING, CONNECT_LIOK, DEAD_MSG_QUEUE
    ONEBOT_PROTOCOL_SIDE = None
    async with CONNECT_LIOK:
        if not ONEBOT_PROTOCOL_SIDE:
            while True:
                try:
                    ONEBOT_PROTOCOL_SIDE = await websockets.connect(
                        f"ws://{APP_SETTING.to.host}:{APP_SETTING.to.port}",
                        max_size=None,
                    )
                except:  # noqa: E722
                    pass
                if not ONEBOT_PROTOCOL_SIDE:  # noqa: E722
                    logger.warning(
                        f"connect to server {APP_SETTING.to.host}:{APP_SETTING.to.port} failed, retry after 5 seconds"
                    )
                    await asyncio.sleep(5)
                    continue
                else:
                    logger.success(
                        f"connect to backend server: {ONEBOT_PROTOCOL_SIDE.remote_address}"
                    )
                    # 重发死信
                    for message in DEAD_MSG_QUEUE:
                        await ONEBOT_PROTOCOL_SIDE.send(message)
                    else:
                        DEAD_MSG_QUEUE.clear()
                    break


LAST_HEARTBEAT_TIME = 0
"""上次收到心跳包的时间"""

ALIVE_CHECK_ENABLE = False
"""心跳检测开关"""

ALIVE_CHECK_LOCK = asyncio.Lock()
"""异步锁，避免多次发出心跳检测请求"""


async def alive_check():
    """
    定时检测心跳
    """
    global LAST_HEARTBEAT_TIME, ALIVE_CHECK_ENABLE, ALIVE_CHECK_LOCK, APP_SETTING
    # 第一次开启心跳检测，将标志位值真，后续如果再走此函数，不再重复开启
    async with ALIVE_CHECK_LOCK:
        if not ALIVE_CHECK_ENABLE:
            ALIVE_CHECK_ENABLE = True
            while True:
                if time.time() - LAST_HEARTBEAT_TIME > APP_SETTING.server.dead_check:
                    logger.warning("heartbeat timeout, waiting for reconnect")
                    await reconnect_server()
                else:
                    # 每30秒检测一次心跳
                    await asyncio.sleep(30)


async def handle_client(websocket: ServerConnection):
    """
    处理客户端连接，将客户端连接转发到后端WebSocket服务器
    """
    # 将客户端连接加入到列表
    global ONEBOT_PROTOCOL_SIDE, LANG_SERVICE_SIDE_SET, APP_SETTING, BOT_ID

    LANG_SERVICE_SIDE_SET.add(websocket)
    logger.success(f"connect from client: {websocket.remote_address}")
    if ONEBOT_PROTOCOL_SIDE:
        await websocket.send(
            json.dumps(
                {
                    "time": int(time.time()),
                    "self_id": BOT_ID,
                    "post_type": "meta_event",
                    "meta_event_type": "lifecycle",
                    "sub_type": "connect",
                }
            )
        )

    # 创建任务，用于转发客户端消息到后端WebSocket服务器
    task = asyncio.create_task(client_to_server(websocket))
    _, _ = await asyncio.wait([task])


async def process_response(_: ServerConnection, request: Request, response: Response):
    global BOT_ID
    response.headers["Content-Type"] = "application/json"
    response.headers["X-Self-ID"] = str(BOT_ID)
    request.headers["Content-Type"] = "application/json"
    request.headers["X-Self-ID"] = str(BOT_ID)


async def main():
    """
    启动WebSocket服务器
    """

    # 连接到后端WebSocket服务器
    global ONEBOT_PROTOCOL_SIDE, APP_SETTING
    if not ONEBOT_PROTOCOL_SIDE:
        await reconnect_server()
        # 启动任务，用于转发后端WebSocket服务器消息到客户端
        asyncio.create_task(server_to_client())

    # 启动WebSocket服务器，监听指定端口
    async with websockets.serve(
        handle_client,
        APP_SETTING.server.host,
        APP_SETTING.server.port,
        max_size=None,
        process_response=process_response,
    ) as server:
        logger.success(
            f"start server at {APP_SETTING.server.host}:{APP_SETTING.server.port}"
        )
        await server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
