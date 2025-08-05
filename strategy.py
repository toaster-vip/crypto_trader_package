import numpy as np
import pandas as pd
from config import CONFIG
from log_utils import log_debug

def get_top_gainers_and_volume(api, top_n=30):
    """
    :param api: 统一传入已初始化的交易所接口实例（如 KuCoinClient）
    :return: USDT 热门候选币列表
    """
    all_tickers = api.get_all_tickers()  # {symbol: {"changeRate":xx, "volValue":xx, ...}}
    if not all_tickers:
        log_debug("未获取到任何行情，热点榜为空！")
        return []
    # 排序，取涨幅和成交量前N
    sorted_gainers = sorted(all_tickers.items(), key=lambda x: float(x[1]['changeRate']), reverse=True)
    gainers_24h = [s for s, v in sorted_gainers[:top_n] if s.endswith('USDT')]
    sorted_volume = sorted(all_tickers.items(), key=lambda x: float(x[1]['volValue']), reverse=True)
    vol_top = [s for s, v in sorted_volume[:top_n] if s.endswith('USDT')]
    # 交集为候选池，不足时并集补足
    candidates = list(set(gainers_24h) & set(vol_top))
    if len(candidates) < top_n // 2:
        candidates = list(set(gainers_24h + vol_top))[:top_n]
    log_debug(f"热点候选池: {candidates}")
    return candidates

def get_klines(api, symbol, interval='1hour', limit=100):
    """
    :param api: 统一传入已初始化的交易所接口实例
    """
    df = api.get_klines(symbol, interval, limit)
    if df is None or len(df) == 0:
        return None
    for col in ['open', 'close', 'high', 'low', 'volume', 'turnover']:
        if col in df:
            df[col] = df[col].astype(float)
    return df

def get_symbol_score(api, symbol):
    """
    :param api: 统一传入已初始化的交易所接口实例
    """
    df = get_klines(api, symbol, '1hour', 100)
    if df is None or len(df) < CONFIG["MIN_KLINE_ROWS"]:
        return {"score": 0, "turnover": 0, "open": 0, "is_new_coin": True, "is_extreme": False}
    open_24h = df['open'].iloc[-24] if len(df) >= 24 else df['open'].iloc[0]
    close_now = df['close'].iloc[-1]
    pct_24h = (close_now - open_24h) / (open_24h + CONFIG['EPS'])
    open_4h = df['open'].iloc[-4] if len(df) >= 4 else df['open'].iloc[0]
    pct_4h = (close_now - open_4h) / (open_4h + CONFIG['EPS'])
    vol_spike = df['volume'].iloc[-6:].mean() / (df['volume'].mean() + CONFIG['EPS'])
    score = 2*pct_24h + 1.5*pct_4h + 1.0*vol_spike
    is_extreme = abs(pct_4h) > CONFIG["EXTREME_PCT_THRESHOLD"]
    return {
        "score": float(score),
        "turnover": float(df['turnover'].iloc[-1]),
        "open": float(df['open'].iloc[-1]),
        "is_new_coin": False,
        "is_extreme": is_extreme,
    }