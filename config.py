CONFIG = {
    "KUCOIN_API_KEY": "688990c9c714e80001ef1a2c",
    "KUCOIN_API_SECRET": "473367a6-af01-48d2-8b78-2817ab879dc1",
    "KUCOIN_API_PASSPHRASE": "ilovesophia",

    "SIMULATE": True,
    "SERVER_CHAN_KEY": "SCT290772THBFAsWEtLa29M3l98qRSZ1DZ",

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
    "LOG_DIR": "/home/linuxuser/trade_logs/",

    "REBALANCE": {
        "HOLD_THRESHOLD_RANK": 10,         # 前10名以内持仓继续持有
        "SCORE_DIFF_THRESHOLD": 0.10,      # 分数差异不足10%，继续持有
        "REQUIRE_CONSISTENT_ROUNDS": 2     # 连续两轮出现才买入
    },

    "RUN_MODE": {
        "TEST_MODE": False,         # ✅ 设置 True 表示只分析前 30 个币
        "BATCH_SIZE": 50,          # 每批处理数量
        "MAX_WORKERS": 10,         # 并发线程数
        "BATCH_DELAY": 1,          # 每批之间的延迟秒数
        "REPORT_INTERVAL": 200     # 每多少轮发送盈亏报告
    }
}

# 保持兼容性（旧模块使用）
KUCOIN_API_KEY = CONFIG["KUCOIN_API_KEY"]
KUCOIN_API_SECRET = CONFIG["KUCOIN_API_SECRET"]
KUCOIN_API_PASSPHRASE = CONFIG["KUCOIN_API_PASSPHRASE"]
SIMULATE = CONFIG["SIMULATE"]
SERVER_CHAN_KEY = CONFIG["SERVER_CHAN_KEY"]
TRADE = CONFIG["TRADE"]
STRATEGY = CONFIG["STRATEGY"]
LOG_DIR = CONFIG["LOG_DIR"]