# strategy.py

import time
import numpy as np
import pandas as pd
import requests
from config import STRATEGY

def get_klines(symbol, interval='1hour', limit=100, max_retries=3):
    url = "https://api.kucoin.com/api/v1/market/candles"
    params = {
        "symbol": symbol,
        "type": interval
    }
    for attempt in range(max_retries):
        time.sleep(0.10)
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                wait_time = 1 ** (attempt + 1)
                print(f"[WARN] 请求过快（429），等待 {wait_time}s 重试 {symbol}")
                time.sleep(wait_time)
                continue
            resp.raise_for_status()
            candles = resp.json().get("data", [])
            if not candles:
                print(f"[WARN] 无K线数据：{symbol}")
                return None
            df = pd.DataFrame(candles, columns=['t', 'o', 'c', 'h', 'l', 'v', 'turnover'])
            df = df.sort_values(by='t')
            df['close'] = df['c'].astype(float)
            df['high'] = df['h'].astype(float)
            df['low'] = df['l'].astype(float)
            df['volume'] = df['v'].astype(float)
            return df
        except Exception as e:
            print(f"[ERROR] 获取K线失败 {symbol}: {e}")
            time.sleep(1)
    print(f"[ERROR] 多次重试失败，放弃：{symbol}")
    return None

# === 策略函数 ===

def score_rsi(df):
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    avg_gain = up.rolling(14).mean()
    avg_loss = down.rolling(14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    if rsi.iloc[-1] < 30:
        return 1
    elif rsi.iloc[-1] > 70:
        return -1
    return 0

def score_macd(df):
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        return 1
    elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        return -1
    return 0

def score_ma(df):
    ma_short = df['close'].rolling(5).mean()
    ma_long = df['close'].rolling(20).mean()
    if ma_short.iloc[-1] > ma_long.iloc[-1] and ma_short.iloc[-2] <= ma_long.iloc[-2]:
        return 1
    elif ma_short.iloc[-1] < ma_long.iloc[-1] and ma_short.iloc[-2] >= ma_long.iloc[-2]:
        return -1
    return 0

def score_momentum(df):
    recent = df['close'].iloc[-1]
    past_avg = df['close'].rolling(10).mean().iloc[-2]
    if recent > past_avg * 1.02:
        return 1
    elif recent < past_avg * 0.98:
        return -1
    return 0

def score_adx(df, period=14):
    high = df['high']
    low = df['low']
    close = df['close']
    plus_dm = high.diff()
    minus_dm = low.diff()
    plus_dm[plus_dm < 0] = 0
    minus_dm[minus_dm > 0] = 0
    tr1 = high - low
    tr2 = abs(high - close.shift())
    tr3 = abs(low - close.shift())
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * (plus_dm.rolling(period).mean() / atr)
    minus_di = abs(100 * (minus_dm.rolling(period).mean() / atr))
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di)) * 100
    adx = dx.rolling(period).mean()
    if adx.iloc[-1] > 25:
        return 1
    elif adx.iloc[-1] < 15:
        return -1
    return 0

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
    obv_slope = df['obv'].diff().rolling(5).mean()
    if obv_slope.iloc[-1] > 0:
        return 1
    elif obv_slope.iloc[-1] < 0:
        return -1
    return 0

def score_cci(df, period=20):
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    cci = (tp - ma) / (0.015 * md)
    if cci.iloc[-1] > 100:
        return 1
    elif cci.iloc[-1] < -100:
        return -1
    return 0

def score_kdj(df):
    low_min = df['low'].rolling(9).min()
    high_max = df['high'].rolling(9).max()
    rsv = (df['close'] - low_min) / (high_max - low_min) * 100
    k = rsv.ewm(com=2).mean()
    d = k.ewm(com=2).mean()
    j = 3 * k - 2 * d
    if j.iloc[-1] > 80:
        return -1
    elif j.iloc[-1] < 20:
        return 1
    return 0

def score_sar(df, af_step=0.02, af_max=0.2):
    high = df['high']
    low = df['low']
    close = df['close']
    sar = close.copy()
    trend = True
    ep = low[0]
    af = af_step
    for i in range(2, len(close)):
        if trend:
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
            if low[i] < sar[i]:
                trend = False
                sar[i] = ep
                ep = high[i]
                af = af_step
        else:
            sar[i] = sar[i - 1] + af * (ep - sar[i - 1])
            if high[i] > sar[i]:
                trend = True
                sar[i] = ep
                ep = low[i]
                af = af_step
        if trend:
            if high[i] > ep:
                ep = high[i]
                af = min(af + af_step, af_max)
        else:
            if low[i] < ep:
                ep = low[i]
                af = min(af + af_step, af_max)
    if close.iloc[-1] > sar.iloc[-1]:
        return 1
    elif close.iloc[-1] < sar.iloc[-1]:
        return -1
    return 0

def score_bollinger(df, period=20, num_std=2):
    close = df['close']
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    if close.iloc[-1] > upper.iloc[-1]:
        return 1
    elif close.iloc[-1] < lower.iloc[-1]:
        return -1
    return 0

def score_volume_spike(df, window=20, spike_threshold=2.0):
    recent_volume = df['volume'].iloc[-1]
    avg_volume = df['volume'].rolling(window).mean().iloc[-2]
    if avg_volume == 0:
        return 0
    ratio = recent_volume / avg_volume
    if ratio > spike_threshold:
        return 1
    return 0

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

    print(f"📊 策略评分 {symbol}: {scores} ➜ 总分: {round(total, 2)}")
    return round(total, 2)

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