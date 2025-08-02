import time
import numpy as np
import pandas as pd
import requests
from config import STRATEGY

def get_klines(symbol, interval='1hour', limit=100, max_retries=3, idx=None, total=None):
    url = "https://api.kucoin.com/api/v1/market/candles"
    params = {
        "symbol": symbol,
        "type": interval
    }
    for attempt in range(max_retries):
        if idx is not None and total is not None and attempt == 0:
            print(f"\r[⏳] 获取K线 {idx+1}/{total}: {symbol}", end="", flush=True)
        time.sleep(0.15)
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
            if len(df) < 30:
                print(f"\n[⚠️] 数据不足（仅 {len(df)} 行）：{symbol}")
                return None
            return df
        except Exception as e:
            print(f"\n[🛑] 获取K线失败 {symbol}: {e}")
            time.sleep(1)
    print(f"\n[❌] 多次重试失败，放弃：{symbol}")
    return None

# --- 各项指标评分函数同你原代码，省略重复 ---

# 省略这里，保留你原有的score_rsi等函数，实现保持一致

# === 综合评分 ===

def get_symbol_score(symbol, idx=None, total=None):
    df = get_klines(symbol, idx=idx, total=total)
    if df is None or len(df) < 30:
        return {
            "score": 0,
            "volume": 0,
            "turnover": 0,
            "open": 0,
            "is_new_coin": True,    # 新币直接标记True
            "is_extreme": False
        }
    # 判断新币（成交量均值低于阈值，可调整阈值）
    VOLUME_THRESHOLD = 50  # 你可以调整阈值，单位与数据对应
    is_new_coin = df['volume'].iloc[-30:].mean() < VOLUME_THRESHOLD

    # 判断极端行情（近一根涨跌幅超过阈值）
    PCT_THRESHOLD = 0.3  # 30%涨跌幅，可调整
    recent_pct_change = (df['close'].iloc[-1] - df['open'].iloc[-1]) / (df['open'].iloc[-1] + 1e-6)
    is_extreme = abs(recent_pct_change) > PCT_THRESHOLD

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
    total_score = 0
    for key, score in scores.items():
        weight = STRATEGY.get(f"{key.upper()}_WEIGHT", 0)
        total_score += score * weight

    return {
        "score": round(total_score, 3),
        "volume": float(df['volume'].iloc[-1]),
        "turnover": float(df['turnover'].iloc[-1]),
        "open": float(df['open'].iloc[-1]),
        "is_new_coin": is_new_coin,
        "is_extreme": is_extreme
    }

# 包装器保持不变
def wrap_with_timing_and_cooldown(fn):
    def wrapper(*args, **kwargs):
        print(f"\n⏱️ 开始全币种评分分析...")
        start = time.time()
        result = fn(*args, **kwargs)
        duration = time.time() - start
        print(f"\n✅ 本轮评分完成，用时：{duration:.2f} 秒")
        print("🌙 冷却中：等待 10 秒避免触发 KuCoin 限速...")
        time.sleep(10)
        return result
    return wrapper