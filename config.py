# config.py
import os
from dotenv import load_dotenv
load_dotenv()

CONFIG = {
    # --- 策略核心参数 ---
    "HOT_TOP_N": 30,
    "TOP_N": 3,
    "MIN_TURNOVER_1H": 5000,
    "MIN_KLINE_ROWS": 36,
    "EPS": 1e-8,

    # --- 盈亏风控 ---
    "TAKE_PROFIT": 0.09,
    "STOP_LOSS": -0.06,
    "TRAILING_STOP_PCT": 0.025,
    "EXTREME_PCT_THRESHOLD": 0.25,

    # --- 仓位/买入控制 ---
    "MAX_POSITION_RATIO": 0.33,
    "MIN_BUY_AMOUNT": 5,       # 作为 minFunds 兜底
    "COOLDOWN_ROUNDS": 3,

    # --- 市场趋势过滤（新增）---
    "MARKET_FILTER_ENABLED": True,
    "MARKET_FILTER_BASE": ["BTC-USDT", "ETH-USDT"],  # 同时看 BTC/ETH
    "MARKET_MA_WINDOW_HOURS": 20,                    # 1hK线的MA窗口
    "MARKET_MAX_DD_24H": -0.03,                      # 24h最大跌幅阈值（-3%）
    "MARKET_SOFTEN_FACTOR": 0.5,                     # 市场差时，TOP_N * 0.5 取整（至少1）

    # --- 并发与性能 ---
    "DEFAULT_WORKERS": 10,
    "WORKER_SLEEP": 0.15,

    # --- 回测与模拟 ---
    "DRY_RUN": False,
    "SIMULATE": False,
    "SIM_START_BALANCE": 120,

    # --- 日志与推送 ---
    "LOG_DIR": "logs",
    "LOG_DETAIL": True,   # False 时压缩快照输出
    "LOG_LEVEL": "INFO",

    # --- KuCoin API ---
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

    # --- 推送KEY ---
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
}

LOG_DIR = CONFIG.get("LOG_DIR", "logs")