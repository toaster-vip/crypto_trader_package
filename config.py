# config.py
import os
import threading
from typing import Any


class _ConfigSingleton:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if not cls._instance:
            with cls._lock:
                if not cls._instance:
                    cls._instance = super().__new__(cls)
                    cls._instance._load_defaults()
        return cls._instance

    def _load_defaults(self):
        self._config = {
            # 策略核心参数
            "HOT_TOP_N": 30,
            "TOP_N": 3,
            "MIN_TURNOVER_1H": 5000,
            "MIN_KLINE_ROWS": 36,
            "EPS": 1e-8,

            # 盈亏风控
            "TAKE_PROFIT": 0.09,
            "STOP_LOSS": -0.06,
            "TRAILING_STOP_PCT": 0.025,
            "EXTREME_PCT_THRESHOLD": 0.25,

            # 仓位/买入控制
            "MAX_POSITION_RATIO": 0.33,
            "MIN_BUY_AMOUNT": 5,
            "COOLDOWN_ROUNDS": 3,

            # 并发与性能
            "DEFAULT_WORKERS": 10,
            "WORKER_SLEEP": 0.15,

            # 回测与模拟
            "DRY_RUN": False,
            "SIMULATE": False,
            "SIM_START_BALANCE": 120,

            # 日志与推送
            "LOG_DIR": "logs",
            "LOG_DETAIL": True,
            "LOG_LEVEL": "INFO",

            # KuCoin API
            "KUCOIN_API_KEY": os.getenv("KUCOIN_API_KEY", ""),
            "KUCOIN_API_SECRET": os.getenv("KUCOIN_API_SECRET", ""),
            "KUCOIN_API_PASSPHRASE": os.getenv("KUCOIN_API_PASSPHRASE", ""),

            # 通知推送
            "SERVER_CHAN_KEY": os.getenv("SERVER_CHAN_KEY", ""),
        }

    def get(self, key: str, default: Any = None) -> Any:
        return self._config.get(key, default)

    def set(self, key: str, value: Any):
        self._config[key] = value

    def all(self) -> dict:
        return self._config.copy()

    def __getitem__(self, key):
        return self.get(key)

    def __setitem__(self, key, value):
        self.set(key, value)


# ✅ 对外暴露实例
config = _ConfigSingleton()
LOG_DIR = config.get("LOG_DIR", "logs")