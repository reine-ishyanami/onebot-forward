import yaml
from pydantic import BaseModel



class Server(BaseModel):
    host: str
    port: int
    dead_check: int = 40
    """心跳检测间隔，单位秒"""


class Logger(BaseModel):
    level: str = "INFO"
    """日志级别"""


class App(BaseModel):
    server: Server
    """服务配置"""
    to: Server
    """转发目标"""
    logger: Logger
    """日志配置"""
    blacklist: list[int] = []
    """黑名单"""
    whitelist: list[int] = []
    """白名单"""


with open("app.yaml", "r") as file:
    data: dict = yaml.safe_load(file)
    APP_SETTING = App(**data)
    """应用配置"""