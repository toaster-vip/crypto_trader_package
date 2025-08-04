import time
import numpy as np
import pandas as pd
import requests
from config import CONFIG

def get_klines(symbol, interval='1hour', limit=100, max_retries=None, idx=None, total=None):
    url = "https://api.kucoin.com/api/v1/market/candles"
    params = {
        "symbol": symbol,
        "type": interval
    }
    retries = max_retries or CONFIG["MAX_RETRIES"]
    for attempt in range(retries):
        if idx is not None and total is not None and attempt == 0:
            print(f"\r[⏳] 获取K线 {idx+1}/{total}: {symbol}", end="", flush=True)
        time.sleep(CONFIG["WORKER_SLEEP"])
        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code == 429:
                wait_time = 2 ** (attempt + 1)
                print(f"\n[⚠️] 请求过快（429），等待 {wait_time}s 后重试：{symbol}")
                time.sleep(wait_time)
                continue
            if resp.status_code != 200:
                print(f"\n[❌] 状态码错误 {resp.status_code}：{symbol}，内容：{resp.text}")
                continue
            data = resp.json()
            candles = data.get("data", [])
            if not candles or not isinstance(candles, list):
                print(f"\n[⚠️] 无效K线数据：{symbol}，返回：{data}")
                return None
            df = pd.DataFrame(candles, columns=['t', 'o', 'c', 'h', 'l', 'v', 'turnover'])
            df = df.sort_values(by='t')
            df['open'] = df['o'].astype(float)
            df['close'] = df['c'].astype(float)
            df['high'] = df['h'].astype(float)
            df['low'] = df['l'].astype(float)
            df['volume'] = df['v'].astype(float)
            df['turnover'] = df['turnover'].astype(float)
            if len(df) < CONFIG["MIN_KLINE_ROWS"]:
                print(f"\n[⚠️] 数据不足（仅 {len(df)} 行）：{symbol}")
                return None
            return df
        except Exception as e:
            print(f"\n[🛑] 获取K线失败 {symbol}: {e}")
            time.sleep(1)
    print(f"\n[❌] 多次重试失败，放弃：{symbol}")
    return None

# ========== 策略打分函数（全部参数变量化）==========

def score_rsi(df):
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    period = CONFIG["RSI_PERIOD"]
    avg_gain = up.rolling(period).mean()
    avg_loss = down.rolling(period).mean()
    rs = avg_gain / (avg_loss + CONFIG["EPS"])
    rsi = 100 - (100 / (1 + rs))
    val = rsi.iloc[-1]
    if val < 30:
        return min(1.0, (30 - val) / 30)
    elif val > 70:
        return -min(1.0, (val - 70) / 30)
    return 0

def score_macd(df):
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    diff = macd.iloc[-1] - signal.iloc[-1]
    return max(-1, min(1, diff / (df['close'].iloc[-1] + CONFIG["EPS"])))

def score_ma(df):
    short = CONFIG["MA_SHORT"]
    long = CONFIG["MA_LONG"]
    ma_short = df['close'].rolling(short).mean()
    ma_long = df['close'].rolling(long).mean()
    diff = ma_short.iloc[-1] - ma_long.iloc[-1]
    return max(-1, min(1, diff / (df['close'].iloc[-1] + CONFIG["EPS"])))

def score_momentum(df):
    win = CONFIG["MOMENTUM_WIN"]
    recent = df['close'].iloc[-1]
    past_avg = df['close'].rolling(win).mean().iloc[-2]
    diff = (recent - past_avg) / (past_avg + CONFIG["EPS"])
    return max(-1, min(1, diff * 5))

def score_adx(df, period=None):
    period = period or CONFIG["RSI_PERIOD"]
    high, low, close = df['high'], df['low'], df['close']
    plus_dm = (high.diff()).clip(lower=0)
    minus_dm = (-low.diff()).clip(lower=0)
    tr = pd.concat([
        high - low,
        abs(high - close.shift()),
        abs(low - close.shift())
    ], axis=1).max(axis=1)
    atr = tr.rolling(period).mean()
    plus_di = 100 * plus_dm.rolling(period).mean() / (atr + CONFIG["EPS"])
    minus_di = 100 * minus_dm.rolling(period).mean() / (atr + CONFIG["EPS"])
    dx = (abs(plus_di - minus_di) / (plus_di + minus_di + CONFIG["EPS"])) * 100
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
    slope = pd.Series(obv).diff().rolling(5).mean().iloc[-1]
    return max(-1, min(1, slope / (np.mean(obv[-10:]) + CONFIG["EPS"])))

def score_cci(df, period=None):
    period = period or CONFIG["CCI_PERIOD"]
    tp = (df['high'] + df['low'] + df['close']) / 3
    ma = tp.rolling(period).mean()
    md = tp.rolling(period).apply(lambda x: np.mean(np.abs(x - np.mean(x))))
    denom = CONFIG["CCI_DENOM"]
    cci = (tp - ma) / (denom * md + CONFIG["EPS"])
    val = cci.iloc[-1]
    return max(-1, min(1, val / 200))

def score_kdj(df):
    com = CONFIG["KDJ_COM"]
    low_min = df['low'].rolling(9).min()
    high_max = df['high'].rolling(9).max()
    rsv = (df['close'] - low_min) / (high_max - low_min + CONFIG["EPS"]) * 100
    k = rsv.ewm(com=com).mean()
    d = k.ewm(com=com).mean()
    j = 3 * k - 2 * d
    val = max(0, min(100, j.iloc[-1]))
    return max(-1, min(1, (50 - val) / 50))

def score_sar(df):
    close = df['close']
    trend = close.iloc[-1] > close.iloc[-2]
    diff = abs(close.iloc[-1] - close.iloc[-2]) / (close.iloc[-2] + CONFIG["EPS"])
    return round(diff if trend else -diff, 3)

def score_bollinger(df, period=None, num_std=None):
    period = period or CONFIG["MA_LONG"]
    num_std = num_std or CONFIG["NUM_STD"]
    close = df['close']
    ma = close.rolling(period).mean()
    std = close.rolling(period).std()
    upper = ma + num_std * std
    lower = ma - num_std * std
    val = close.iloc[-1]
    if val > upper.iloc[-1]:
        return (val - upper.iloc[-1]) / (std.iloc[-1] + CONFIG["EPS"])
    elif val < lower.iloc[-1]:
        return (val - lower.iloc[-1]) / (std.iloc[-1] + CONFIG["EPS"])
    return 0

def score_volume_spike(df, window=None, spike_threshold=2.0):
    window = window or CONFIG["VOLUME_WIN"]
    vol_now = df['volume'].iloc[-1]
    vol_avg = df['volume'].rolling(window).mean().iloc[-2]
    ratio = vol_now / (vol_avg + CONFIG["EPS"])
    return min(1.0, ratio - 1.0) if ratio > spike_threshold else 0

# 综合评分与过滤（也变量化判据）

def get_symbol_score(symbol, idx=None, total=None):
    df = get_klines(symbol, idx=idx, total=total)
    if df is None or len(df) < CONFIG["MIN_KLINE_ROWS"]:
        return {
            "score": 0,
            "volume": 0,
            "turnover": 0,
            "open": 0,
            "is_new_coin": True,
            "is_extreme": False
        }
    # 新币/极端行情判定
    is_new_coin = df['volume'].iloc[-30:].mean() < CONFIG["NEW_COIN_VOLUME"]
    recent_pct_change = (df['close'].iloc[-1] - df['open'].iloc[-1]) / (df['open'].iloc[-1] + CONFIG["EPS"])
    is_extreme = abs(recent_pct_change) > CONFIG["EXTREME_PCT_THRESHOLD"]

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
    # 权重用config单独加（如有）
    total_score = sum(scores.values())  # 可自行在config添加每项权重
    return {
        "score": round(total_score, 3),
        "volume": float(df['volume'].iloc[-1]),
        "turnover": float(df['turnover'].iloc[-1]),
        "open": float(df['open'].iloc[-1]),
        "is_new_coin": is_new_coin,
        "is_extreme": is_extreme
    }