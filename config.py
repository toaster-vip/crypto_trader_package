# config.py
import os
from dotenv import load_dotenv
load_dotenv()

CONFIG = {
    # --- 策略核心参数 ---
    "HOT_TOP_N": 20,          # 原30 -> 20：减噪音、集中头部
    "TOP_N": 2,               # 原3 -> 2：100刀更合适，避免摊薄
    "MIN_TURNOVER_1H": 80000, # 原5000 -> 80,000 USDT：抬高流动性门槛防滑点
    "MIN_KLINE_ROWS": 48,     # 原36 -> 48：至少2天K线，减少新币风险
    "EPS": 1e-8,

    # --- 盈亏风控 ---
    "TAKE_PROFIT": 0.07,         # 原0.09 -> 0.07：更快锁盈，降低回吐
    "STOP_LOSS": -0.04,          # 原-0.06 -> -0.04：更快止损，单笔亏控在本金<2%
    "TRAILING_STOP_PCT": 0.018,  # 原0.025 -> 0.018：有浮盈后更紧跟踪
    "EXTREME_PCT_THRESHOLD": 0.20, # 原0.25 -> 0.20：剔除过度剧烈波动的票
    "TAKE_PROFIT_EXIT_PCT": 1.0,   # 新增：非热点止盈退出比例（1.0=全仓止盈，0.5=卖一半）

    # --- 仓位/买入控制 ---
    "MAX_POSITION_RATIO": 0.45,  # 原0.33 -> 0.45：两仓合计~90%，留10%机动/手续费
    "MIN_BUY_AMOUNT": 5,         # 作为 minFunds 兜底
    "COOLDOWN_ROUNDS": 3,

    # --- 市场趋势过滤（新增）---
    "MARKET_FILTER_ENABLED": True,
    "MARKET_FILTER_BASE": ["BTC-USDT", "ETH-USDT"],
    "MARKET_MA_WINDOW_HOURS": 24,  # 原20 -> 24：1天窗口，抗噪更强
    "MARKET_MAX_DD_24H": -0.04,    # 原-0.03 -> -0.04：不过度避险，避免错过行情
    "MARKET_SOFTEN_FACTOR": 0.5,   # 市况差时缩小TOP_N并加严筛选

    # --- 并发与性能 ---
    "DEFAULT_WORKERS": 8,   # 原10 -> 8：够用且更稳，降低被限流概率
    "WORKER_SLEEP": 0.15,

    # --- 回测与模拟 ---
    "DRY_RUN": False,
    "SIMULATE": False,
    "SIM_START_BALANCE": 120,

    # --- 日志与推送 ---
    "LOG_DIR": "logs",
    "LOG_DETAIL": False,   # 原True -> False：压缩快照输出，更易读
    "LOG_LEVEL": "INFO",

    # --- KuCoin API ---
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

    # --- 推送KEY ---
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
}

LOG_DIR = CONFIG.get("LOG_DIR", "logs")