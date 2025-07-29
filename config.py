CONFIG = {
    "API_KEY": "s7GzS87EZgTjSzgjG71fQo",  # ✅ 你的真实 API Key
    "API_SECRET": "cxakp_wZMVxFLmonyfWar4HhVy7f",  # ✅ 你的真实 API Secret
   # "BASE_URL": "https://api.crypto.com/v2",  # ✅ Crypto.com Exchange API（正式交易用）
    "BASE_URL": "https://api.crypto.com/exchange/v1/",

    "SIMULATE": False,  # ⛔ 已启用真实交易模式（False 为真实，True 为模拟）

    "SERVER_CHAN_KEY": "SCT290772THBFAsWEtLa29M3l98qRSZ1DZ",  # ✅ Server酱通知推送

    # 若为空则系统自动识别持仓币种并轮动交易
    "SYMBOLS": [],

    # 策略权重分配：总和为 1.0
    "STRATEGY_WEIGHTS": {
        "ma": 0.4,
        "rsi": 0.3,
        "macd": 0.3
    },

    # 策略打分阈值
    "THRESHOLDS": {
        "buy": 0.2,   # >0.2 执行买入
        "sell": -0.2  # <-0.2 执行卖出
    },

    # 止盈/止损参数
    "TAKE_PROFIT": 0.045,   # ✅ +4.5% 止盈
    "STOP_LOSS": -0.025     # ✅ -2.5% 止损
}

# ✅ 以下为兼容其他模块的全局变量映射（不建议改名）
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
SIMULATION_MODE = CONFIG["SIMULATE"]

# ✅ 新增字段：日志保存目录
LOG_DIR = "/home/linuxuser/trade_logs/"