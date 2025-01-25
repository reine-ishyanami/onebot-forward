import asyncio
import sys
import websockets
from config import APP_SETTING
from loguru import logger

from websockets.asyncio.client import ClientConnection
from websockets.asyncio.server import ServerConnection
from websockets.typing import Data

from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import aiosmtplib

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from loguru import Record

logger.remove()

# 配置日志文件
logger.add(
    "logs/forward.log",
    rotation="100 MB",
    compression="zip",
    format="{time:YYYY-MM-DD HH:mm:ss:SSS} | {level} | {name}:{function}:{line} | {message}",
    encoding="utf-8",
    enqueue=True,
    level=APP_SETTING.logger.level.file.upper(),
)


def format_log_message(record: "Record") -> str:
    """格式化日志消息"""
    current_time = record.get("time").strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    level = record.get("level").name

    msg_max_len = 200

    name = record.get("name")
    function = record.get("function")
    line = record.get("line")
    msg = record.get("message")
    msg = msg.replace("{", "{{").replace("}", "}}")
    etc = "..." if len(msg) > msg_max_len else ""
    ret = f"<green>{current_time}</green> | "
    ret += f"<level>{level:<7}</level>  | "
    ret += f"<cyan>{name}:{function}:{line}</cyan> - "
    ret += f"<level>{msg[:msg_max_len]}{etc}</level>\n"
    return ret


# 配置控制台输出
logger.add(
    sys.stderr,
    format=format_log_message,
    colorize=True,
    level=APP_SETTING.logger.level.console.upper(),
)


def send_by_auth(gid: int) -> bool:
    """判断是否转发此消息"""
    if len(APP_SETTING.whitelist) > 0:
        # 如果群号属于白名单，放行
        if gid in APP_SETTING.whitelist:
            logger.info(f"forward message from {gid} in whitelist")
            return True
        else:
            logger.debug(f"ignore message from {gid} not in whitelist")
            return False
    if len(APP_SETTING.blacklist) > 0:
        # 如果群号属于黑名单，拦截
        if gid in APP_SETTING.blacklist:
            logger.info(f"ignore message from {gid} in blacklist")
            return False
        else:
            logger.debug(f"forward message from {gid} not in blacklist")
            return True
    return True


async def forward_message(
    client: ServerConnection | ClientConnection, message: Data
) -> bool:
    """转发消息"""
    try:
        await client.send(message)
        return True
    except websockets.ConnectionClosed:
        logger.warning("failed to send message")
        return False


async def send_notice_email(id: str):
    """发送掉线通知邮件
    
    Args:
        id (str): bot id
    """
    mail_config = APP_SETTING.notice
    if not mail_config.enable:
        return
    mail = mail_config.mail
    message = MIMEMultipart("alternative")
    message["Subject"] = Header(mail.title, 'utf-8') # type: ignore
    message["From"] = mail_config.sender
    message["To"] = mail_config.receiver
    content = mail.content.format(bot_id=id)
    message.attach(MIMEText(content))
    # 连接SMTP服务器并发送邮件
    use_tls = False
    if mail_config.port == 465:
        use_tls = True
    try:
        async with aiosmtplib.SMTP(hostname=mail_config.smtp, port=mail_config.port, use_tls=use_tls) as smtp:
            await smtp.login(mail_config.sender, mail_config.password)
            await smtp.send_message(message)
    except Exception as e:
        err = f"邮件发送失败，错误信息如下{e}"
        return err
    logger.info("通知邮件发送成功!")
    return


if __name__ == "__main__":
    asyncio.run(send_notice_email("1234567890"))