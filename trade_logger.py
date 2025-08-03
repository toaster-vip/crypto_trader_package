# ================== trade_logger.py ==================
# 所有日志参数都可用 config 管理（如 LOG_DIR 路径等）

import os
import json
import threading
from datetime import datetime
from config import LOG_DIR

_log_lock = threading.Lock()

def get_logfile_path():
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"{today}.jsonl")

def log_event(event: dict):
    event['ts'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _log_lock:
        with open(get_logfile_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

def log_round_snapshot(round_info: dict):
    log_event({"type": "round_snapshot", **round_info})

def log_trade(trade: dict):
    log_event({"type": "trade", **trade})

def log_rebalance(rebalance_info: dict):
    log_event({"type": "rebalance", **rebalance_info})

def log_error(error_msg: str, context: dict = None):
    err = {"type": "error", "error": error_msg}
    if context:
        err.update(context)
    log_event(err)