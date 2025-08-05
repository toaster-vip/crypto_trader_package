# log_utils.py
import os
import json
import pandas as pd
from datetime import datetime
from config import LOG_DIR

os.makedirs(LOG_DIR, exist_ok=True)

def log_snapshot(balances, price_map, tag="snapshot", date_str=None):
    date_str = date_str or datetime.now().strftime("%Y%m%d_%H%M%S")
    file = os.path.join(LOG_DIR, f"snapshot_{tag}_{date_str}.json")
    data = {
        "time": date_str,
        "balances": balances,
        "prices": price_map,
    }
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

def log_trade_detail(trade):
    date_str = datetime.now().strftime("%Y%m%d")
    file = os.path.join(LOG_DIR, f"trades_{date_str}.jsonl")
    with open(file, "a") as f:
        f.write(json.dumps(trade, ensure_ascii=False) + "\n")

def log_info(msg):
    print(f"[INFO] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}")

def log_error(msg):
    print(f"[ERROR] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}")

def log_debug(msg):
    print(f"[DEBUG] {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} {msg}")