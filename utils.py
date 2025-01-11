import sys
from config import APP_SETTING
from loguru import logger


logger.remove()

logger.add(sys.stdout, level=APP_SETTING.logger.level.upper())

def send_by_auth(gid: int) -> bool:
    """判断是否转发此消息"""
    if len(APP_SETTING.whitelist) > 0:
        # 如果群号属于白名单，放行
        if gid in APP_SETTING.whitelist:
            logger.info(f"receive message from {gid} in whitelist, forward")
            return True
        else:
            return False
    if len(APP_SETTING.blacklist) > 0 :
        # 如果群号属于黑名单，拦截
        if gid in APP_SETTING.blacklist:
            logger.info(f"receive message from {gid} in blacklist, ignore")
            return False
        else:
            return True
    return True