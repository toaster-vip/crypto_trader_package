# config.py

CONFIG = {
    "API": {
        "KUCOIN_API_KEY": "688990c9c714e80001ef1a2c",
        "KUCOIN_API_SECRET": "473367a6-af01-48d2-8b78-2817ab879dc1",
        "KUCOIN_API_PASSPHRASE": "ilovesophia",
        "BASE_URL": "https://api.kucoin.com"
    },
    "SIMULATE": False,  # 是否为模拟交易模式
    "SERVERCHAN": {
        "ENABLE": True,
        "SEND_KEY": "SCT290772THBFAsWEtLa29M3l98qRSZ1DZ"
    },
    "LOG_DIR": "/home/linuxuser/trade_logs/",
    "TRADE": {
        "TAKE_PROFIT": 0.045,   # 止盈 4.5%
        "STOP_LOSS": -0.025     # 止损 -2.5%
    },
    "STRATEGY": {
        "RSI_WEIGHT": 0.15,
        "MACD_WEIGHT": 0.15,
        "SMA_WEIGHT": 0.10,
        "MOMENTUM_WEIGHT": 0.10,
        "ADX_WEIGHT": 0.10,
        "OBV_WEIGHT": 0.10,
        "CCI_WEIGHT": 0.10,
        "KDJ_WEIGHT": 0.10,
        "SAR_WEIGHT": 0.05,
        "BOLLINGER_WEIGHT": 0.025,
        "VOLUME_WEIGHT": 0.025
    },
    "RESERVE_RATIO": 0.07,  # 预留 USDT 百分比（用于手续费、新币、调仓缓冲等）
}

# 向下兼容映射（旧模块中调用时无需改动）
KUCOIN_API_KEY = CONFIG["API"]["KUCOIN_API_KEY"]
KUCOIN_API_SECRET = CONFIG["API"]["KUCOIN_API_SECRET"]
KUCOIN_API_PASSPHRASE = CONFIG["API"]["KUCOIN_API_PASSPHRASE"]
BASE_URL = CONFIG["API"]["BASE_URL"]
STRATEGY = CONFIG["STRATEGY"]