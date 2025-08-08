import os
import logging
from config import CONFIG

# 日志等级
LOG_LEVEL = CONFIG.get("LOG_LEVEL", "INFO").upper()
LOG_DIR = CONFIG.get("LOG_DIR", "logs")

os.makedirs(LOG_DIR, exist_ok=True)

log_file_path = os.path.join(LOG_DIR, "runtime.log")

# 日志格式
formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s", "%Y-%m-%d %H:%M:%S")

# 控制台 handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# 文件 handler
file_handler = logging.FileHandler(log_file_path, mode='a', encoding='utf-8')
file_handler.setFormatter(formatter)

# 创建 logger
logger = logging.getLogger("TraderLogger")
logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
logger.addHandler(console_handler)
logger.addHandler(file_handler)
logger.propagate = False  # 防止重复输出

# 统一封装函数
def log_info(msg): logger.info(msg)
def log_error(msg): logger.error(msg)
def log_debug(msg): logger.debug(msg)
def log_warning(msg): logger.warning(msg)