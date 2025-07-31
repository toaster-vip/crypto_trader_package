# strategy.py

import time
import numpy as np
import pandas as pd
import requests
from config import STRATEGY

def get_symbol_score(symbol):
    df = get_klines(symbol)
    if df is None or len(df) < 30:
        print(f"[WARN] 跳过评分，数据不足：{symbol}")
        return {
            "score": 0,
            "volume": 0
        }

    scores = {
        "rsi": score_rsi(df),
        "macd": score_macd(df),
        "ma": score_ma(df),
        "momentum": score_momentum(df),
        "adx": score_adx(df),
        "obv": score_obv(df),
        "cci": score_cci(df),
        "kdj": score_kdj(df),
        "sar": score_sar(df),
        "bollinger": score_bollinger(df),
        "volume": score_volume_spike(df)
    }

    total = 0
    for key, score in scores.items():
        weight = STRATEGY.get(f"{key.upper()}_WEIGHT", 0)
        total += score * weight

    print(f"📊 策略评分 {symbol}: {scores} ➜ 总分: {round(total, 3)}")

    return {
        "score": round(total, 3),
        "volume": float(df['volume'].iloc[-1])  # 取最后一根K线的成交量
    }
    
# === 策略函数（打分范围为 -1.0 ~ +1.0） ===

def score_rsi(df):
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    avg_gain = up.rolling(14).mean()
    avg_loss = down.rolling(14).mean()
    rs = avg_gain / (avg_loss + 1e-6)
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    if val < 30:
        return min(1.0, (30 - val) / 30)  # 越小分越高
    elif val > 70:
        return -min(1.0, (val - 70) / 30)
    return 0

def score_macd(df):
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    diff = macd.iloc[-1] - signal.iloc[-1]
    return max(-1, min(1, diff / df['close'].iloc[-1]))

def score_ma(df):
    ma_short = df['close'].rolling(5).mean()
    ma_long = df['close'].rolling(20).mean()
    diff = ma_short.iloc[-1] - ma_long.iloc[-1]
    return max(-1, min(1, diff / df['close'].iloc[-1]))

def score_momentum(df):
    recent = df['close'].iloc[-1]
    past_avg = df['close'].rolling(10).mean().iloc[-2]
    diff = (recent - past_avg) / past_avg
    return max(-1, min(1, diff * 5))  # 放大倍数但控制范围

def score_adx(df, period=14):
    high, low, close = df['high'], df['low'], df['close']
    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr = pd.concat([
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift())
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * plus_dm.rolling(period).mean() / (atr + 1e-6)
    minus_di = 100 * minus_dm.rolling(period).mean() / (atr + 1e-6)
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + 1e-6)) * 100
    adx = dx.rolling(period).mean()
    score = (adx.iloc[-1] - 20) / 25
    return max(-1, min(1, score))

def score_obv(df):
    obv = [0]
    for i in range(1, len(df)):
        if df['close'].iloc[i] > df['close'].iloc[i - 1]:
            obv.append(obv[-1] + df['volume'].iloc[i])
        elif df['close'].iloc[i] < df['close'].iloc[i - 1]:
            obv.append(obv[-1] - df['volume'].iloc[i])
        else:
            obv.append(obv[-1])
    df['obv'] = obv
    slope = pd.Series(obv).diff().rolling(5).mean().iloc[-1]
    return max(-1, min(1, slope / (np.mean(obv[-10:]) + 1e-6)))

def score_cci(df, period=20):
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    cci = (tp - ma) / (0.015 * md + 1e-6)
    val = cci.iloc[-1]
    return max(-1, min(1, val / 200))

def score_kdj(df):
    low_min = df['low'].rolling(9).min()
    high_max = df['high'].rolling(9).max()
    rsv = (df['close'] - low_min) / (high_max - low_min + 1e-6) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d
    val = j.iloc[-1]
    if val < 0: val = 0
    if val > 100: val = 100
    return max(-1, min(1, (50 - val) / 50))

def score_sar(df):
    close = df['close']
    trend = close.iloc[-1] > close.iloc[-2]
    diff = abs(close.iloc[-1] - close.iloc[-2]) / (close.iloc[-2] + 1e-6)
    return round(diff if trend else -diff, 3)

def score_bollinger(df, period=20, num_std=2):
    close = df['close']
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    val = close.iloc[-1]
    if val > upper.iloc[-1]:
        return (val - upper.iloc[-1]) / std.iloc[-1]
    elif val < lower.iloc[-1]:
        return (val - lower.iloc[-1]) / std.iloc[-1]
    return 0

def score_volume_spike(df, window=20, spike_threshold=2.0):
    vol_now = df['volume'].iloc[-1]
    vol_avg = df['volume'].rolling(window).mean().iloc[-2]
    ratio = vol_now / (vol_avg + 1e-6)
    return min(1.0, ratio - 1.0) if ratio > spike_threshold else 0

# === 综合评分 ===

def get_symbol_score(symbol):
    df = get_klines(symbol)
    if df is None or len(df) < 30:
        print(f"[WARN] 跳过评分，数据不足：{symbol}")
        return 0

    scores = {
        "rsi": score_rsi(df),
        "macd": score_macd(df),
        "ma": score_ma(df),
        "momentum": score_momentum(df),
        "adx": score_adx(df),
        "obv": score_obv(df),
        "cci": score_cci(df),
        "kdj": score_kdj(df),
        "sar": score_sar(df),
        "bollinger": score_bollinger(df),
        "volume": score_volume_spike(df)
    }

    total = 0
    for key, score in scores.items():
        weight = STRATEGY.get(f"{key.upper()}_WEIGHT", 0)
        total += score * weight

    print(f"📊 策略评分 {symbol}: {scores} ➜ 总分: {round(total, 3)}")
    return round(total, 3)

# === 包装器 ===

def wrap_with_timing_and_cooldown(fn):
    def wrapper(*args, **kwargs):
        print(f"\n⏱️ 开始全币种评分分析...")
        start = time.time()
        result = fn(*args, **kwargs)
        duration = time.time() - start
        print(f"✅ 本轮评分完成，用时：{duration:.2f} 秒")
        print("🌙 冷却中：等待 10 秒避免触发 KuCoin 限速...")
        time.sleep(10)
        return result
    return wrapper