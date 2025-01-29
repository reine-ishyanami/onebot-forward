from typing import Optional
import yaml
from pydantic import BaseModel


class Server(BaseModel):
    host: str
    port: int


class Level(BaseModel):
    """日志级别"""

    console: str = "INFO"
    file: str = "WARNING"


class Logger(BaseModel):
    level: Level = Level()
    """日志级别"""


class Mail(BaseModel):
    """邮件内容配置"""

    title: str = "你的Bot掉线了"
    """邮件标题"""
    subject: str = "OneBot 掉线通知"
    """邮件主题"""
    content: str = "OneBot 掉线通知：\n\n({bot_id}) 掉线了，请及时处理。"
    """邮件内容"""


class Notice(BaseModel):
    """邮件通知配置"""

    smtp: str
    """SMTP服务器地址"""
    port: int = 465
    """SMTP服务器端口"""
    sender: str
    """发件人邮箱地址"""
    password: str
    """发件人邮箱密码"""
    receiver: str
    """收件人邮箱地址"""
    mail: Mail = Mail()
    """邮件内容配置"""


class App(BaseModel):
    server: Server
    """服务配置"""
    to: Server
    """转发目标"""
    dead_check: int = 40
    """心跳检测间隔，单位秒，0表示不检测"""
    logger: Logger = Logger()
    """日志配置"""
    blacklist: list[int] = []
    """黑名单"""
    whitelist: list[int] = []
    """白名单"""
    notice: Optional[Notice] = None
    """邮件通知配置"""


with open("app.yaml", "r") as file:
    data: dict = yaml.safe_load(file)
    APP_SETTING = App(**data)
    """应用配置"""
