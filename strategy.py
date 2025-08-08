import numpy as np
import pandas as pd
from config import CONFIG
from log_utils import log_debug


def get_top_gainers_and_volume(api, top_n=30, exclude_symbols=None):
    """
    获取涨幅和成交额前N的币种列表（过滤USDT交易对，支持冷却/黑名单过滤）

    :param api: 已初始化的 KuCoinClient
    :param top_n: 热门池容量
    :param exclude_symbols: set，可选，需过滤的币对（如冷却池/黑名单）
    :return: 选出的一组 symbol（字符串列表）
    """
    all_tickers = api.get_all_tickers()  # {symbol: {"changeRate":xx, "volValue":xx, ...}}
    if not all_tickers:
        log_debug("未获取到任何行情，热点榜为空！")
        return []

    exclude_symbols = set(exclude_symbols or [])

    # 排序前top_n涨幅和成交额
    sorted_gainers = sorted(all_tickers.items(), key=lambda x: float(x[1]['changeRate']), reverse=True)
    sorted_volume = sorted(all_tickers.items(), key=lambda x: float(x[1]['volValue']), reverse=True)

    gainers_24h = [s for s, _ in sorted_gainers[:top_n] if s.endswith('USDT')]
    vol_top = [s for s, _ in sorted_volume[:top_n] if s.endswith('USDT')]

    # 交集为核心候选池
    candidates = list(set(gainers_24h) & set(vol_top))
    if len(candidates) < top_n // 2:
        candidates = list(set(gainers_24h + vol_top))[:top_n]

    # 冷却或黑名单剔除
    filtered = [s for s in candidates if s not in exclude_symbols]
    log_debug(f"热点候选池: {filtered}")
    return filtered


def get_klines(api, symbol, interval='1hour', limit=100):
    """
    封装统一 K 线获取方法（返回 Pandas DataFrame）

    :param api: 交易所 API 实例
    :param symbol: 币种名（如 GOATS-USDT）
    :param interval: K线周期
    :param limit: 最多K线数
    :return: pd.DataFrame 或 None
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
    对某个币种进行评分，结果用于选币。

    :param api: 已初始化的 KuCoinClient
    :param symbol: 币种对，如“GOATS-USDT”
    :return: dict {score, turnover, open, is_new_coin, is_extreme}
    """
    df = get_klines(api, symbol, '1hour', 100)

    if df is None or len(df) < CONFIG["MIN_KLINE_ROWS"]:
        return {
            "score": 0,
            "turnover": 0,
            "open": 0,
            "is_new_coin": True,
            "is_extreme": False
        }

    try:
        open_24h = df['open'].iloc[-24] if len(df) >= 24 else df['open'].iloc[0]
        open_4h = df['open'].iloc[-4] if len(df) >= 4 else df['open'].iloc[0]
        close_now = df['close'].iloc[-1]

        pct_24h = (close_now - open_24h) / (open_24h + CONFIG['EPS'])
        pct_4h = (close_now - open_4h) / (open_4h + CONFIG['EPS'])

        # 成交量爆发度（近6根与全局均值比）
        vol_spike = df['volume'].iloc[-6:].mean() / (df['volume'].mean() + CONFIG['EPS'])

        # 简化评分：涨幅 + 成交量强度
        score = 2 * pct_24h + 1.5 * pct_4h + 1.0 * vol_spike

        is_extreme = abs(pct_4h) > CONFIG["EXTREME_PCT_THRESHOLD"]

        return {
            "score": float(score),
            "turnover": float(df['turnover'].iloc[-1]),
            "open": float(df['open'].iloc[-1]),
            "is_new_coin": False,
            "is_extreme": is_extreme,
        }

    except Exception as e:
        log_debug(f"[评分异常] {symbol}: {e}")
        return {
            "score": 0,
            "turnover": 0,
            "open": 0,
            "is_new_coin": True,
            "is_extreme": False
        }