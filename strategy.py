# strategy.py
import numpy as np
import pandas as pd
import requests
from config import STRATEGY_WEIGHTS

def get_klines(symbol, interval='1h', limit=100):
    """
    获取历史K线数据（用于技术指标分析）
    """
    url = "https://api.crypto.com/v2/public/get-candlestick"
    params = {
        "instrument_name": symbol,
        "interval": interval,
        "limit": limit
    }
    try:
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        candles = data.get("result", {}).get("data", [])
        df = pd.DataFrame(candles, columns=['t', 'o', 'h', 'l', 'c', 'v'])
        df = df.sort_values(by='t')  # 时间升序
        df['close'] = df['c'].astype(float)
        return df
    except Exception as e:
        print(f"[ERROR] 获取K线数据失败: {e}")
        return None


# --- 策略函数 ---

def score_rsi(df):
    """
    RSI指标（14期）：70超买（考虑卖），30超卖（考虑买）
    """
    delta = df['close'].diff()
    up = delta.clip(lower=0)
    down = -1 * delta.clip(upper=0)
    avg_gain = up.rolling(14).mean()
    avg_loss = down.rolling(14).mean()
    rs = avg_gain / avg_loss
    rsi = 100 - (100 / (1 + rs))
    if rsi.iloc[-1] < 30:
        return 1  # 买
    elif rsi.iloc[-1] > 70:
        return -1  # 卖
    return 0

def score_macd(df):
    """
    MACD指标：快慢线交叉
    """
    ema12 = df['close'].ewm(span=12).mean()
    ema26 = df['close'].ewm(span=26).mean()
    macd = ema12 - ema26
    signal = macd.ewm(span=9).mean()
    if macd.iloc[-1] > signal.iloc[-1] and macd.iloc[-2] <= signal.iloc[-2]:
        return 1  # 金叉买入
    elif macd.iloc[-1] < signal.iloc[-1] and macd.iloc[-2] >= signal.iloc[-2]:
        return -1  # 死叉卖出
    return 0

def score_ma(df):
    """
    均线策略：短均线上穿长均线为买入信号
    """
    ma_short = df['close'].rolling(5).mean()
    ma_long = df['close'].rolling(20).mean()
    if ma_short.iloc[-1] > ma_long.iloc[-1] and ma_short.iloc[-2] <= ma_long.iloc[-2]:
        return 1
    elif ma_short.iloc[-1] < ma_long.iloc[-1] and ma_short.iloc[-2] >= ma_long.iloc[-2]:
        return -1
    return 0

def score_momentum(df):
    """
    动量策略：当前价格是否显著高于过去N期均值
    """
    recent = df['close'].iloc[-1]
    past_avg = df['close'].rolling(10).mean().iloc[-2]
    if recent > past_avg * 1.02:
        return 1
    elif recent < past_avg * 0.98:
        return -1
    return 0


# --- 综合评分计算 ---

def get_symbol_score(symbol):
    df = get_klines(symbol)
    if df is None or len(df) < 30:
        print(f"[WARN] 跳过评分，数据不足：{symbol}")
        return 0

    scores = {}
    scores["rsi"] = score_rsi(df)
    scores["macd"] = score_macd(df)
    scores["ma"] = score_ma(df)
    scores["momentum"] = score_momentum(df)

    total = 0
    for key, score in scores.items():
        weight = STRATEGY_WEIGHTS.get(key, 0)
        total += score * weight

    print(f"📊 策略评分 {symbol}: {scores} ➜ 总分: {round(total, 2)}")
    return round(total, 2)