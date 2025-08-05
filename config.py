# config.py
import os

CONFIG = {
    # 热门币池等策略参数（如前）
    "HOT_TOP_N": 30,
    "TOP_N": 3,
    "MIN_TURNOVER_1H": 5000,
    "MIN_KLINE_ROWS": 36,
    "EPS": 1e-8,
    "TAKE_PROFIT": 0.07,
    "STOP_LOSS": -0.045,
    "TRAILING_STOP_PCT": 0.025,
    "MAX_POSITION_RATIO": 0.33,
    "MIN_BUY_AMOUNT": 5,
    "EXTREME_PCT_THRESHOLD": 0.25,
    "COOLDOWN_AFTER_LOSS": 3,
    "DEFAULT_WORKERS": 10,
    "WORKER_SLEEP": 0.15,
    "DRY_RUN": False,
    "SIMULATE": True,
    "SIM_START_BALANCE": 100,
    "LOG_DIR": "logs",
    "LOG_DETAIL": True,
    "LOG_LEVEL": "INFO",

    # --- KuCoin API 密钥（推荐用环境变量）---
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

    # --- ServerChan/企业微信等推送KEY（同样推荐环境变量注入）---
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
}

LOG_DIR = CONFIG.get("LOG_DIR", "logs")