import os

CONFIG = {
    # === 策略参数 ===
    "HOT_TOP_N": 30,           # 热点榜数量
    "TOP_N": 3,                # 最终持仓数量
    "MIN_TURNOVER_1H": 5000,   # 1小时成交额（USDT）
    "MIN_KLINE_ROWS": 36,      # 最小K线行数
    "EPS": 1e-8,               # 防除零
    "TAKE_PROFIT": 0.07,       # 止盈线 7%
    "STOP_LOSS": -0.045,       # 止损线 -4.5%
    "TRAILING_STOP_PCT": 0.025,# 移动止损
    "MAX_POSITION_RATIO": 0.33,# 单币最大占用资金比
    "MIN_BUY_AMOUNT": 5,       # 最小买入金额
    "EXTREME_PCT_THRESHOLD": 0.25,  # 极端行情过滤

    # === 冷却机制 ===
    "COOLDOWN_AFTER_PROFIT": 2,  # 止盈后冷却轮数
    "COOLDOWN_AFTER_LOSS": 4,    # 止损后冷却轮数

    # === 多线程参数 ===
    "DEFAULT_WORKERS": 10,
    "WORKER_SLEEP": 0.15,

    # === 运行模式 ===
    "DRY_RUN": False,
    "SIMULATE": False,
    "SIM_START_BALANCE": 100,

    # === 日志/推送 ===
    "LOG_DIR": "logs",
    "LOG_DETAIL": True,
    "LOG_LEVEL": "INFO",

    # === KuCoin API 密钥（建议环境变量注入）===
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

    # === 推送Key（如ServerChan等）===
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
}

LOG_DIR = CONFIG.get("LOG_DIR", "logs")