import os
from typing import Any


class Config:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Config, cls).__new__(cls)
            cls._instance._init_config()
        return cls._instance

    def _init_config(self):
        self._config = {
            # === 策略核心参数 ===
            "HOT_TOP_N": 30,          # 热门币池数量
            "TOP_N": 3,               # 最终选币数量
            "MIN_TURNOVER_1H": 5000,  # 1小时最小成交额，过滤流动性差的币
            "MIN_KLINE_ROWS": 36,     # 至少36根K线（1.5天），用于过滤新币
            "EPS": 1e-8,              # 防除零精度

            # === 盈亏风控 ===
            "TAKE_PROFIT": 0.09,           # 止盈 +9%
            "STOP_LOSS": -0.06,            # 止损 -6%
            "TRAILING_STOP_PCT": 0.025,    # 移动止损百分比（预留）
            "EXTREME_PCT_THRESHOLD": 0.25, # 4小时波动超过25%剔除

            # === 仓位与买入控制 ===
            "MAX_POSITION_RATIO": 0.33,   # 单币最大仓位比例
            "MIN_BUY_AMOUNT": 5,          # 最小买入金额（USDT）
            "COOLDOWN_ROUNDS": 3,         # 冷却轮数（止盈/止损后）

            # === 并发控制 ===
            "DEFAULT_WORKERS": 10,     # 多线程评分线程数
            "WORKER_SLEEP": 0.15,      # 多线程sleep时间，防止限流

            # === 模拟与回测 ===
            "DRY_RUN": False,              # 是否仿真运行（不下单）
            "SIMULATE": False,             # 是否使用模拟账户
            "SIM_START_BALANCE": 120,      # 模拟账户初始资金

            # === 日志与推送 ===
            "LOG_DIR": "logs",
            "LOG_DETAIL": True,
            "LOG_LEVEL": "INFO",

            # === API 密钥（可使用环境变量）===
            "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
            "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
            "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

            # === 推送Key（如Server酱、企业微信）===
            "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
        }

        self.LOG_DIR = self._config.get("LOG_DIR", "logs")
        os.makedirs(self.LOG_DIR, exist_ok=True)

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value

    def as_dict(self) -> dict:
        return dict(self._config)


# 兼容旧代码：
CONFIG = Config()
LOG_DIR = CONFIG.LOG_DIR