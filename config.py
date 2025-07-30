CONFIG = {
    "KUCOIN_API_KEY": "688990c9c714e80001ef1a2c",  # ✅ 新 Key
    "KUCOIN_API_SECRET": "473367a6-af01-48d2-8b78-2817ab879dc1",  # ✅ 新 Secret
    "KUCOIN_API_PASSPHRASE": "ilovesophia",

    "SIMULATE": True,  # ✅ 模拟交易模式
    "SERVER_CHAN_KEY": "SCT290772THBFAsWEtLa29M3l98qRSZ1DZ",

    "TRADE": {
        "TAKE_PROFIT": 0.045,   # 止盈 +4.5%
        "STOP_LOSS": -0.025     # 止损 -2.5%
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

    "RESERVE_RATIO": 0.07,  # ✅ 保留 7% USDT 不参与买入，用于手续费、行情反转等缓冲

    "LOG_DIR": "/home/linuxuser/trade_logs/"
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