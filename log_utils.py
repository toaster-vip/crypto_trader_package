# log_utils.py
import os
import json
import logging
import threading
from datetime import datetime
from logging.handlers import RotatingFileHandler
from config import LOG_DIR, CONFIG

# === 路径与常量 ===
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, "main_trader.log")
EVENTS_FILE = os.path.join(LOG_DIR, "events.jsonl")

_JSON_LOCK = threading.Lock()
_LOGGER_NAME = "ctp"  # crypto trader package

_LEVEL_MAP = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}

def _level_from_config():
    lvl = str(CONFIG.get("LOG_LEVEL", "INFO")).upper()
    return _LEVEL_MAP.get(lvl, logging.INFO)

def init_logger(level: str | None = None):
    """
    只在进程启动时调用一次：
        from log_utils import init_logger
        init_logger(CONFIG.get("LOG_LEVEL"))
    """
    logger = logging.getLogger(_LOGGER_NAME)
    if logger.handlers:
        return logger  # 已初始化

    logger.setLevel(_level_from_config() if level is None else _LEVEL_MAP.get(level.upper(), logging.INFO))

    fmt = logging.Formatter("[%(levelname)s] %(asctime)s %(message)s", datefmt="%Y-%m-%d %H:%M:%S")

    # 控制台
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    logger.addHandler(sh)

    # 滚动文件：5MB * 5 份
    fh = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # 降低第三方库的噪音
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("requests").setLevel(logging.WARNING)

    return logger

def _get_logger():
    return logging.getLogger(_LOGGER_NAME)

# === 封装的便捷日志方法（兼容旧代码）===
def log_info(msg: str):
    _get_logger().info(msg)

def log_error(msg: str):
    _get_logger().error(msg)

def log_debug(msg: str):
    # 只有在 LOG_LEVEL=DEBUG 时会真正落盘/打印
    _get_logger().debug(msg)

# === 结构化 JSON 事件 ===
def _append_event(event: dict):
    event = dict(event) if event else {}
    event.setdefault("ts", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    with _JSON_LOCK:
        with open(EVENTS_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

def log_trade_detail(trade: dict):
    """
    结构化交易明细 -> logs/events.jsonl（type=trade）
    """
    e = {"type": "trade", **(trade or {})}
    _append_event(e)
    # 同时在人类可读日志里打一条简短信息
    sym = trade.get("symbol", "?")
    side = trade.get("type", "?")
    price = trade.get("price", "NA")
    amt = trade.get("amount", "NA")
    log_info(f"[Trade] {side} {sym} amt={amt} px={price}")

def log_snapshot(balances: dict, price_map: dict, tag: str = "snapshot", meta: dict | None = None):
    """
    结构化资产/价格快照 -> logs/events.jsonl（type=snapshot）
    不再生成一堆独立 JSON 文件，避免日志碎片。
    """
    e = {
        "type": "snapshot",
        "tag": tag,
        "balances": balances or {},
        "prices": price_map or {},
    }
    if meta:
        e["meta"] = meta
    _append_event(e)
    # 简要人类日志
    usdt = (balances or {}).get("USDT", 0)
    log_info(f"[Snapshot:{tag}] USDT={usdt} balances_keys={list((balances or {}).keys())[:6]} prices_keys={list((price_map or {}).keys())[:6]}")

# 额外：统一记录一次性结构化事件（调仓结果、错误等）
def log_event(event_type: str, **kwargs):
    e = {"type": event_type}
    e.update(kwargs or {})
    _append_event(e)