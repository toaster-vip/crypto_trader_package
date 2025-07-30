# config.py

CONFIG = {
    # === KuCoin API 凭证 ===
    "KUCOIN_API_KEY": "688990c9c714e80001ef1a2c",
    "KUCOIN_API_SECRET": "473367a6-af01-48d2-8b78-2817ab879dc1",
    "KUCOIN_API_PASSPHRASE": "ilovesophia",

    # === 模式设置 ===
    "SIMULATE": False,  # False = 实盘交易；True = 模拟测试

    # === 通知设置 ===
    "SERVER_CHAN_KEY": "SCT290772THBFAsWEtLa29M3l98qRSZ1DZ",  # Server酱

    # === 策略权重（总分 = 策略分数 * 权重）===
    "STRATEGY_WEIGHTS": {
        "rsi": 0.3,
        "macd": 0.3,
        "ma": 0.2,
        "momentum": 0.2,
    },

    # === 止盈止损设置 ===
    "TAKE_PROFIT": 0.045,   # +4.5%
    "STOP_LOSS": -0.025,    # -2.5%

    # === 日志设置 ===
    "LOG_DIR": "/home/linuxuser/trade_logs/",

    # === 邮件通知（暂未启用） ===
    "EMAIL_RECEIVER": "toaster.vip@gmail.com",
}

# 向后兼容原始字段
KUCOIN_API_KEY = CONFIG["KUCOIN_API_KEY"]
KUCOIN_API_SECRET = CONFIG["KUCOIN_API_SECRET"]
KUCOIN_API_PASSPHRASE = CONFIG["KUCOIN_API_PASSPHRASE"]
SIMULATE = CONFIG["SIMULATE"]
SERVER_CHAN_KEY = CONFIG["SERVER_CHAN_KEY"]
STRATEGY_WEIGHTS = CONFIG["STRATEGY_WEIGHTS"]
TAKE_PROFIT = CONFIG["TAKE_PROFIT"]
STOP_LOSS = CONFIG["STOP_LOSS"]
LOG_DIR = CONFIG["LOG_DIR"]