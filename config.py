# config.py
import os
from dotenv import load_dotenv
load_dotenv()

CONFIG = {
    # === 核心选币规模 ===
    "HOT_TOP_N": 20,      # 热点池最大候选
    "TOP_N": 2,           # 实际建仓数量（小资金更集中）

    # === 基本门槛（已适度下调）===
    # 之前 80,000 → 40,000：在冷清时段也能选出标的
    "MIN_TURNOVER_1H": 40000,
    # 之前 48 → 36：允许新一点的币进入评估（仍有 1.5 天数据）
    "MIN_KLINE_ROWS": 36,
    "EPS": 1e-8,

    # === 盈亏风控 ===
    "TAKE_PROFIT": 0.07,
    "STOP_LOSS": -0.04,
    "TRAILING_STOP_PCT": 0.018,
    "EXTREME_PCT_THRESHOLD": 0.20,
    # 非热点触达止盈后的退出比例：1.0=全清，0.5=卖半仓
    "TAKE_PROFIT_EXIT_PCT": 1.0,

    # === 仓位/买入控制 ===
    "MAX_POSITION_RATIO": 0.45,   # 单次分配上限（相对剩余USDT）
    "MIN_BUY_AMOUNT": 5,          # 交易所 minFunds 兜底
    "COOLDOWN_ROUNDS": 3,         # 冷却轮数（每轮≈4小时）

    # === 市场趋势过滤 ===
    "MARKET_FILTER_ENABLED": True,
    "MARKET_FILTER_BASE": ["BTC-USDT", "ETH-USDT"],
    "MARKET_MA_WINDOW_HOURS": 24,
    "MARKET_MAX_DD_24H": -0.04,
    "MARKET_SOFTEN_FACTOR": 0.5,  # 市况差时自动收紧 TOP_N 的比例

    # === 4 小时同频硬过滤（已降门槛 + 支持动态放宽）===
    "USE_4H_FILTER": True,
    # 基础阈值（稍降）：4h 涨幅 ≥ 0.3%，最后1h 收盘站上 EMA(6)，近6根均量 ≥ 全均量的 1.05x
    "MIN_PCT_4H": 0.003,
    "EMA_WINDOW_1H": 6,
    "REQUIRE_LAST1H_ABOVE_EMA": True,
    "MIN_VOL_FACTOR": 1.05,

    # 当候选明显不足时，是否“自动放宽”（strategy 会读取）
    "RELAX_ON_FEW": True,
    # 一次性放宽比例（用于快速补量）：例如 0.6 = 阈值放到 60%
    "RELAX_FACTOR": 0.6,

    # —— 细粒度动态放宽计划（可选：strategy 若实现可逐级使用）——
    # 目标最少候选数（小于该值就进入放宽流程）
    "AUTO_RELAX_ENABLED": True,
    "AUTO_RELAX_MIN_CAND": 6,   # 建议 >= TOP_N*3
    # 放宽阶梯（从上到下依次尝试）
    "AUTO_RELAX_STEPS": [
        {"MIN_PCT_4H_MUL": 0.8, "MIN_VOL_FACTOR_MUL": 0.9,  "MIN_TURNOVER_1H_ABS": 30000, "REQUIRE_EMA": True},
        {"MIN_PCT_4H_MUL": 0.6, "MIN_VOL_FACTOR_MUL": 0.85, "MIN_TURNOVER_1H_ABS": 25000, "REQUIRE_EMA": False},
        {"MIN_PCT_4H_MUL": 0.5, "MIN_VOL_FACTOR_MUL": 0.8,  "MIN_TURNOVER_1H_ABS": 20000, "REQUIRE_EMA": False},
    ],

    # —— 打分阶段的自适应成交额放宽（main_trader 用）——
    # 逐级把 MIN_TURNOVER_1H 乘以这些系数尝试放宽；最终还不够才兜底
    "TURNOVER_RELAX_STEPS": [0.7, 0.5],

    # === 去碎仓/持仓寿命（rebalancer 用）===
    "MAX_HOLD_ROUNDS": 10,   # 超过则触发“寿命退出”（仅小波动时）
    "SMALL_PNL_EXIT": 0.02,  # ±2% 视为小波动
    "MIN_MERGE_AMOUNT": 7,   # 市值<7 USDT 直接清理

    # === 并发与性能 ===
    "DEFAULT_WORKERS": 8,
    "WORKER_SLEEP": 0.15,

    # === 回测与模拟 ===
    "DRY_RUN": False,
    "SIMULATE": False,
    "SIMULATE_START_BALANCE": 120,  # 兼容性：有的模块叫 SIM_START_BALANCE
    "SIM_START_BALANCE": 120,

    # === 日志与推送 ===
    "LOG_DIR": "logs",
    "LOG_DETAIL": False,
    "LOG_LEVEL": "INFO",

    # === KuCoin API ===
    "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
    "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
    "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

    # === Server酱 ===
    "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
}

LOG_DIR = CONFIG.get("LOG_DIR", "logs")