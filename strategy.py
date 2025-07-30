# strategy.py
import time
import numpy as np
import pandas as pd
import requests
from config import STRATEGY

MAX_RETRIES = 3

def get_klines(symbol, interval='1hour', limit=100):
    """
    获取 KuCoin 历史K线数据（带限速与重试）
    """
    url = "https://api.kucoin.com/api/v1/market/candles"
    params = {
        "symbol": symbol,
        "type": interval
    }

    for attempt in range(1, MAX_RETRIES + 1):
        try:
            time.sleep(0.15)  # 控制频率，避免触发 429
            resp = requests.get(url, params=params)
            if resp.status_code == 429:
                wait_time = 2 ** attempt
                print(f"[WARN] 请求过快（429），等待 {wait_time}s 重试第 {attempt}/{MAX_RETRIES} 次：{symbol}")
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
            return df
        except Exception as e:
            print(f"[ERROR] 获取K线失败（第 {attempt} 次）: {e}")
            time.sleep(1)

    print(f"[ERROR] 多次尝试仍失败，放弃：{symbol}")
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
        "momentum": score_momentum(df)
    }

    total = 0
    for key, score in scores.items():
        weight = STRATEGY.get(f"{key.upper()}_WEIGHT", 0)
        total += score * weight

    print(f"📊 策略评分 {symbol}: {scores} ➜ 总分: {round(total, 2)}")
    return round(total, 2)


# === 交易辅助判断 ===

def should_sell(score, threshold=0.2):
    return score < threshold

def check_take_profit_stop_loss(entry_price, current_price, take_profit=0.045, stop_loss=-0.025):
    if entry_price == 0:
        return None
    change = (current_price - entry_price) / entry_price
    if change >= take_profit:
        return 'take_profit'
    elif change <= stop_loss:
        return 'stop_loss'
    return None