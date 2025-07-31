import os

CONFIG = {
    # ✅ 敏感信息：使用环境变量注入
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY"),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET"),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE"),
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY"),

    # ✅ 直接写入的控制项
    "SIMULATE": False,
    "LOG_DIR": "/home/linuxuser/trade_logs/",

    "TRADE": {
        "TAKE_PROFIT": 0.045,
        "STOP_LOSS": -0.025
    },

    "STRATEGY": {
        "MACD_WEIGHT": 0.2,
        "RSI_WEIGHT": 0.1,
        "SMA_WEIGHT": 0.1,
        "MOMENTUM_WEIGHT": 0.1,
        "TREND_WEIGHT": 0.05,
        "ADX_WEIGHT": 0.1,
        "OBV_WEIGHT": 0.1,
        "CCI_WEIGHT": 0.05,
        "KDJ_WEIGHT": 0.05,
        "SAR_WEIGHT": 0.05,
        "BOLLINGER_WEIGHT": 0.05,
        "VOLUME_WEIGHT": 0.05
    },

    "RESERVE_RATIO": 0.07,

    "REBALANCE": {
        "HOLD_THRESHOLD_RANK": 10,
        "SCORE_DIFF_THRESHOLD": 0.10,
        "REQUIRE_CONSISTENT_ROUNDS": 2
    },

    "RUN_MODE": {
        "TEST_MODE": False,
        "BATCH_SIZE": 50,
        "MAX_WORKERS": 10,
        "BATCH_DELAY": 1,
        "REPORT_INTERVAL": 200
    }
}

# 保持兼容性
KUCOIN_API_KEY = CONFIG["KUCOIN_API_KEY"]
KUCOIN_API_SECRET = CONFIG["KUCOIN_API_SECRET"]
KUCOIN_API_PASSPHRASE = CONFIG["KUCOIN_API_PASSPHRASE"]
SIMULATE = CONFIG["SIMULATE"]
SERVER_CHAN_KEY = CONFIG["SERVER_CHAN_KEY"]
TRADE = CONFIG["TRADE"]
STRATEGY = CONFIG["STRATEGY"]
LOG_DIR = CONFIG["LOG_DIR"]