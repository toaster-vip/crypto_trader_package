import os
import json
import threading
from datetime import datetime

LOG_DIR = "trade_logs"
os.makedirs(LOG_DIR, exist_ok=True)
_log_lock = threading.Lock()

def get_logfile_path():
    today = datetime.now().strftime("%Y-%m-%d")
    return os.path.join(LOG_DIR, f"{today}.jsonl")

def log_event(event: dict):
    """写入一条日志（自动加时间）"""
    event['ts'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with _log_lock:
        with open(get_logfile_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")

def log_round_snapshot(round_info: dict):
    """每轮决策全量快照"""
    log_event({"type": "round_snapshot", **round_info})

def log_trade(trade: dict):
    """每笔交易操作日志"""
    log_event({"type": "trade", **trade})

def log_error(error_msg: str, context: dict = None):
    """记录报错"""
    err = {"type": "error", "error": error_msg}
    if context:
        err.update(context)
    log_event(err)