import os

CONFIG = {
    # ====== 账户与敏感信息（环境变量注入，安全第一） ======
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY"),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET"),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE"),
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY"),

    # ====== 运行/日志参数 ======
    "SIMULATE": True,
    "LOG_DIR": "/home/linuxuser/trade_logs/",

    # ====== 资金分配与风控 ======
    "RESERVE_RATIO": 0.12,           # 持续预留12%资金
    "MAX_POSITION_RATIO": 0.18,      # 单币最大18%
    "MAX_HOLD_COUNT": 6,             # 最多持有6个币
    "MIN_BUY_AMOUNT": 5,             # 单次最小买入
    "FIXED_BUY_AMOUNT": 10,          # 默认每次10刀买入

    # ====== 策略参数（专业分权重）======
    "STRATEGY": {
        "MACD_WEIGHT": 0.18,
        "RSI_WEIGHT": 0.12,
        "SMA_WEIGHT": 0.09,
        "MOMENTUM_WEIGHT": 0.09,
        "TREND_WEIGHT": 0.08,
        "ADX_WEIGHT": 0.08,
        "OBV_WEIGHT": 0.08,
        "CCI_WEIGHT": 0.06,
        "KDJ_WEIGHT": 0.05,
        "SAR_WEIGHT": 0.05,
        "BOLLINGER_WEIGHT": 0.05,
        "VOLUME_WEIGHT": 0.07
    },

    # ====== 调仓及风控高级参数 ======
    "TRADE": {
        "TAKE_PROFIT": 0.048,
        "STOP_LOSS": -0.022
    },

    "REBALANCE": {
        "HOLD_THRESHOLD_RANK": 8,
        "SCORE_DIFF_THRESHOLD": 0.13,
        "REQUIRE_CONSISTENT_ROUNDS": 2
    },

    "SIM_START_BALANCE": 100,
    "FEE": {
        "MAKER": 0.001,
        "TAKER": 0.001
    },

    # ====== 批量调度与实盘运行优化 ======
    "RUN_MODE": {
        "TEST_MODE": False,
        "BATCH_SIZE": 25,
        "MAX_WORKERS": 6,
        "BATCH_DELAY": 1,
        "REPORT_INTERVAL": 200
    }
}

# 保持兼容性（所有老代码无缝调用）
KUCOIN_API_KEY = CONFIG["KUCOIN_API_KEY"]
KUCOIN_API_SECRET = CONFIG["KUCOIN_API_SECRET"]
KUCOIN_API_PASSPHRASE = CONFIG["KUCOIN_API_PASSPHRASE"]
SIMULATE = CONFIG["SIMULATE"]
SERVER_CHAN_KEY = CONFIG["SERVER_CHAN_KEY"]
TRADE = CONFIG["TRADE"]
STRATEGY = CONFIG["STRATEGY"]
LOG_DIR = CONFIG["LOG_DIR"]