# config.py
import os
from dotenv import load_dotenv
load_dotenv()


CONFIG = {
    # --- 策略核心参数 ---
    "HOT_TOP_N": 30,          # 热门币池，前30个热点作为候选
    "TOP_N": 3,               # 最终上榜币数量
    "MIN_TURNOVER_1H": 5000,  # 1小时成交额下限，防流动性风险
    "MIN_KLINE_ROWS": 36,     # 至少需要36根K线（1.5天，防新币）
    "EPS": 1e-8,              # 防除零

    # --- 盈亏风控（已根据4小时轮动优化）---
    "TAKE_PROFIT": 0.09,      # 止盈 +9%
    "STOP_LOSS": -0.06,       # 止损 -6%
    "TRAILING_STOP_PCT": 0.025,   # 移动止损百分比，暂未启用可留作高级用
    "EXTREME_PCT_THRESHOLD": 0.25, # 极端波动剔除阈值，避免异常币

    # --- 仓位/买入控制 ---
    "MAX_POSITION_RATIO": 0.33,     # 单币最大仓位比例
    "MIN_BUY_AMOUNT": 5,            # 最小买入USDT，按交易所限制定
    "COOLDOWN_ROUNDS": 3,           # 止盈/止损后冷却几轮（如每4小时1轮，3轮=12小时）

    # --- 并发与性能 ---
    "DEFAULT_WORKERS": 10,     # 多线程评分线程数
    "WORKER_SLEEP": 0.15,      # 多线程sleep，太低会被限流

    # --- 回测与模拟 ---
    "DRY_RUN": False,          # True: 仿真，不实际下单
    "SIMULATE": False,         # True: 虚拟盘仿真
    "SIM_START_BALANCE": 120,  # 仿真初始资金

    # --- 日志与推送 ---
    "LOG_DIR": "logs",
    "LOG_DETAIL": True,
    "LOG_LEVEL": "INFO",

    # --- KuCoin API 密钥（推荐环境变量注入）---
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

    # --- 推送KEY（如企业微信/ServerChan等）---
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
}

LOG_DIR = CONFIG.get("LOG_DIR", "logs")