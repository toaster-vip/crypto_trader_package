# strategy.py
import numpy as np
import pandas as pd
from config import CONFIG
from log_utils import log_debug

def _ma(series, n):
    n = max(1, int(n))
    if len(series) < n:
        return float(series.mean()) if len(series) else 0.0
    return float(pd.Series(series).rolling(n).mean().iloc[-1])

def _pct(a, b, eps=1e-12):  # (a-b)/b
    return float((a - b) / (b + eps))

def is_market_ok(api) -> bool:
    """
    市场过滤：BTC/ETH 1h K线 MA 斜率 & 24h跌幅不劣于阈值
    """
    if not CONFIG.get("MARKET_FILTER_ENABLED", True):
        return True
    bases = CONFIG.get("MARKET_FILTER_BASE", ["BTC-USDT", "ETH-USDT"])
    win = CONFIG.get("MARKET_MA_WINDOW_HOURS", 20)
    worst_dd_limit = CONFIG.get("MARKET_MAX_DD_24H", -0.03)
    oks = []
    for sym in bases:
        df = api.get_klines(sym, "1hour", max(48, win + 4))
        if df is None or len(df) < max(24, win + 2):
            oks.append(False)
            continue
        close = df["close"].astype(float).values
        ma_now = _ma(close, win)
        ma_prev = _ma(close[:-1], win)
        slope_ok = ma_now >= ma_prev  # MA不下行
        dd24 = _pct(close[-1], close[-24])
        dd_ok = dd24 >= worst_dd_limit
        oks.append(slope_ok and dd_ok)
    ok = all(oks) if oks else True
    log_debug(f"市场过滤：bases={bases}, OK={ok}, oks={oks}")
    return ok

def get_top_gainers_and_volume(api, top_n=30, exclude_symbols=None, market_ok=True):
    """
    :return: USDT 热门候选币列表
    """
    all_tickers = api.get_all_tickers()
    if not all_tickers:
        log_debug("未获取到任何行情，热点榜为空！")
        return []
    exclude_symbols = set(exclude_symbols or [])

    # 只看 USDT 现货
    usdt_tickers = {s: v for s, v in all_tickers.items() if s.endswith("USDT")}

    # 排序，涨幅 + 成交额
    sorted_gainers = sorted(usdt_tickers.items(), key=lambda x: float(x[1].get('changeRate', 0.0)), reverse=True)
    gainers_24h = [s for s, _ in sorted_gainers[:top_n]]
    sorted_volume = sorted(usdt_tickers.items(), key=lambda x: float(x[1].get('volValue', 0.0)), reverse=True)
    vol_top = [s for s, _ in sorted_volume[:top_n]]

    # 交集优先，不足用并集补齐
    candidates = list(set(gainers_24h) & set(vol_top))
    if len(candidates) < top_n // 2:
        candidates = list(set(gainers_24h + vol_top))[:top_n]

    # 市场差时“退火”：少选 & 更严
    if not market_ok:
        soften = max(1, int(CONFIG["TOP_N"] * CONFIG.get("MARKET_SOFTEN_FACTOR", 0.5)))
        # 强制 4h 涨幅为正的
        strict = []
        for s in candidates:
            df = api.get_klines(s, '1hour', 8)
            if df is None or len(df) < 4:
                continue
            open_4h = float(df['open'].iloc[-4])
            close_now = float(df['close'].iloc[-1])
            if close_now > open_4h:  # 4h上行
                strict.append(s)
        candidates = (strict[:soften] or candidates[:soften])

    # 冷却/黑名单剔除
    filtered = [s for s in candidates if s not in exclude_symbols]
    log_debug(f"热点候选池: {filtered}")
    return filtered

def get_klines(api, symbol, interval='1hour', limit=100):
    df = api.get_klines(symbol, interval, limit)
    if df is None or len(df) == 0:
        return None
    for col in ['open', 'close', 'high', 'low', 'volume', 'turnover']:
        if col in df:
            df[col] = df[col].astype(float)
    return df

def get_symbol_score(api, symbol):
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