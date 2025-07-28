CONFIG = {
    "API_KEY": "WpWVkahrWSCaJfcmvcJgSv",
    "API_SECRET": "cxakp_FDRiZ8aw9UPogTVTgzzJGv",
    "BASE_URL": "https://api.crypto.com/v2",
    "SIMULATE": False,  # ⛔ 真实交易模式
    "SERVER_CHAN_KEY": "SCT290772THBFAsWEtLa29M3l98qRSZ1DZ",
    "SYMBOLS": [],
    "STRATEGY_WEIGHTS": {
        "ma": 0.4,
        "rsi": 0.3,
        "macd": 0.3
    },
    "THRESHOLDS": {
        "buy": 0.2,
        "sell": -0.2
    },
    "TAKE_PROFIT": 0.045,   # 止盈 +4.5%
    "STOP_LOSS": -0.025     # 止损 -2.5%
}

# 以下是为了兼容其他模块的读取方式（推荐不要改名）
API_KEY = CONFIG["API_KEY"]
API_SECRET = CONFIG["API_SECRET"]
BASE_URL = CONFIG["BASE_URL"]
IS_REAL_TRADING = not CONFIG["SIMULATE"]
SERVER_CHAN_KEY = CONFIG["SERVER_CHAN_KEY"]
SUPPORTED_SYMBOLS = [s.split("_")[0] for s in CONFIG["SYMBOLS"]]
STRATEGY_WEIGHTS = CONFIG["STRATEGY_WEIGHTS"]
THRESHOLDS = CONFIG["THRESHOLDS"]
TAKE_PROFIT = CONFIG["TAKE_PROFIT"]
STOP_LOSS = CONFIG["STOP_LOSS"]