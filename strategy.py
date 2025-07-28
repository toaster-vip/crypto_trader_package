import talib
import numpy as np
from config import CONFIG

price_history = {}

def calculate_signal(symbol, market_data):
    data = market_data.get("result", {}).get("data", [{}])[0]
    price = float(data.get("a", 0))
    history = price_history.setdefault(symbol, [])
    history.append(price)
    prices = np.array(history)
    signals = []
    # MA strategy
    if len(prices) > 10:
        ma_short = talib.SMA(prices, timeperiod=5)[-1]
        ma_long = talib.SMA(prices, timeperiod=10)[-1]
        signals.append(1 if ma_short > ma_long else -1)
    else:
        signals.append(0)
    # RSI strategy
    if len(prices) > 14:
        rsi = talib.RSI(prices, timeperiod=14)[-1]
        signals.append(1 if rsi < 30 else (-1 if rsi > 70 else 0))
    else:
        signals.append(0)
    # Weighted score
    total = 0
    for strat, weight in CONFIG["STRATEGY_WEIGHTS"].items():
        idx = 0 if strat=="ma" else 1
        total += signals[idx] * weight
    if total > CONFIG["THRESHOLDS"]["buy"]:
        return 1
    elif total < CONFIG["THRESHOLDS"]["sell"]:
        return -1
    return 0