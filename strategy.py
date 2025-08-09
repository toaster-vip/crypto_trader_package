# strategy.py
import numpy as np
import pandas as pd
from config import CONFIG
from log_utils import log_debug

# ====== 小工具 ======
def _ma(series, n):
    n = max(1, int(n))
    if len(series) < n:
        return float(series.mean()) if len(series) else 0.0
    return float(pd.Series(series).rolling(n).mean().iloc[-1])

def _ema(series, n):
    n = max(1, int(n))
    if len(series) < n:
        return float(series.mean()) if len(series) else 0.0
    return float(pd.Series(series).ewm(span=n, adjust=False).mean().iloc[-1])

def _pct(a, b, eps=1e-12):  # (a-b)/b
    return float((a - b) / (b + eps))

def _cfg(key, default):
    return CONFIG.get(key, default)

# ====== 市场过滤 ======
def is_market_ok(api) -> bool:
    """
    市场过滤：BTC/ETH 1h K线 MA 斜率 & 24h跌幅不劣于阈值
    """
    if not _cfg("MARKET_FILTER_ENABLED", True):
        return True
    bases = _cfg("MARKET_FILTER_BASE", ["BTC-USDT", "ETH-USDT"])
    win = _cfg("MARKET_MA_WINDOW_HOURS", 24)
    worst_dd_limit = _cfg("MARKET_MAX_DD_24H", -0.04)

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

# ====== 4h 同频过滤参数（可在 config.py 里覆盖）======
USE_4H_FILTER            = _cfg("USE_4H_FILTER", True)
MIN_PCT_4H               = float(_cfg("MIN_PCT_4H", 0.005))     # +0.5% 起步
EMA_WINDOW_1H            = int(_cfg("EMA_WINDOW_1H", 6))        # 近6小时 EMA
REQUIRE_LAST1H_ABOVE_EMA = _cfg("REQUIRE_LAST1H_ABOVE_EMA", True)
MIN_VOL_FACTOR           = float(_cfg("MIN_VOL_FACTOR", 1.1))   # 近6根 / 全部均量
RELAX_ON_FEW             = _cfg("RELAX_ON_FEW", True)
RELAX_FACTOR             = float(_cfg("RELAX_FACTOR", 0.8))     # 阈值宽松 20%
EPS                      = float(_cfg("EPS", 1e-8))

def _passes_4h_filter(api, symbol, pct4h_thresh, vol_factor_thresh, require_above_ema):
    """
    对单个 symbol 的 4h 同频硬过滤：
      1) 4h 涨幅 >= 阈值
      2) 最后一根 close >= EMA(6)（可选）
      3) 近6根均量 / 全样本均量 >= 阈值
    """
    df = api.get_klines(symbol, '1hour', 100)
    if df is None or len(df) < 8:
        return False

    df = df.copy()
    for col in ['open', 'close', 'volume']:
        if col in df:
            df[col] = df[col].astype(float)

    close_now = df['close'].iloc[-1]
    open_4h   = df['open'].iloc[-4]
    pct_4h    = (close_now - open_4h) / (open_4h + EPS)

    ok_pct4h  = (pct_4h >= pct4h_thresh)

    ema6      = _ema(df['close'].values, EMA_WINDOW_1H)
    last_above_ema = (close_now >= (ema6 - 1e-12)) if require_above_ema else True

    vol_6     = df['volume'].iloc[-6:].mean()
    vol_all   = df['volume'].mean()
    vol_factor = float(vol_6 / (vol_all + EPS))
    ok_vol    = (vol_factor >= vol_factor_thresh)

    return bool(ok_pct4h and last_above_ema and ok_vol)

def get_top_gainers_and_volume(api, top_n=30, exclude_symbols=None, market_ok=True):
    """
    :return: USDT 热门候选币列表（已应用 4h 同频硬过滤 + 候选不足自动放宽）
    """
    all_tickers = api.get_all_tickers()
    if not all_tickers:
        log_debug("未获取到任何行情，热点榜为空！")
        return []

    exclude_symbols = set(exclude_symbols or [])
    usdt_tickers = {s: v for s, v in all_tickers.items() if s.endswith("USDT")}

    # 24h 涨幅 & 成交额
    sorted_gainers = sorted(usdt_tickers.items(), key=lambda x: float(x[1].get('changeRate', 0.0)), reverse=True)
    gainers_24h    = [s for s, _ in sorted_gainers[:top_n]]

    sorted_volume  = sorted(usdt_tickers.items(), key=lambda x: float(x[1].get('volValue', 0.0)), reverse=True)
    vol_top        = [s for s, _ in sorted_volume[:top_n]]

    # 基础候选：交集优先，不足并集补齐
    candidates = list(set(gainers_24h) & set(vol_top))
    if len(candidates) < top_n // 2:
        candidates = list(set(gainers_24h + vol_top))[:top_n]

    # —— 市况差时“退火”：少选且更严（保留原逻辑，但后续仍会做4h硬过滤）——
    if not market_ok:
        soften = max(1, int(_cfg("TOP_N", 2) * _cfg("MARKET_SOFTEN_FACTOR", 0.5)))
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

    # —— 4h 同频硬过滤（可开关）——
    filtered = [s for s in candidates if s not in exclude_symbols]
    if USE_4H_FILTER and filtered:
        pct4h_thresh = MIN_PCT_4H
        volf_thresh  = MIN_VOL_FACTOR
        require_ema  = REQUIRE_LAST1H_ABOVE_EMA

        hard = [s for s in filtered if _passes_4h_filter(api, s, pct4h_thresh, volf_thresh, require_ema)]

        # 候选不足自动放宽
        min_need = max(_cfg("TOP_N", 2), max(1, top_n // 4))
        if RELAX_ON_FEW and len(hard) < min_need:
            pct4h_relaxed = pct4h_thresh * RELAX_FACTOR     # 阈值放宽 20%
            volf_relaxed  = volf_thresh * RELAX_FACTOR
            hard_relaxed  = [s for s in filtered if _passes_4h_filter(api, s, pct4h_relaxed, volf_relaxed, require_ema)]
            # 合并去重，优先保留严格筛到的
            seen = set(hard)
            hard = hard + [s for s in hard_relaxed if s not in seen]

        filtered = hard

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
    """
    打分同频化：提高 4h 权重。
    score = 1.2 * pct_24h + 2.0 * pct_4h + 1.0 * vol_spike
    其中 vol_spike = 近6根均量 / 全量均量
    """
    df = get_klines(api, symbol, '1hour', 100)
    if df is None or len(df) < _cfg("MIN_KLINE_ROWS", 48):
        return {"score": 0, "turnover": 0, "open": 0, "is_new_coin": True, "is_extreme": False}

    open_24h   = df['open'].iloc[-24] if len(df) >= 24 else df['open'].iloc[0]
    close_now  = df['close'].iloc[-1]
    pct_24h    = (close_now - open_24h) / (open_24h + EPS)

    open_4h    = df['open'].iloc[-4] if len(df) >= 4 else df['open'].iloc[0]
    pct_4h     = (close_now - open_4h) / (open_4h + EPS)

    vol_spike  = df['volume'].iloc[-6:].mean() / (df['volume'].mean() + EPS)

    # 提权后的打分
    score = 1.2 * pct_24h + 2.0 * pct_4h + 1.0 * vol_spike

    is_extreme = abs(pct_4h) > _cfg("EXTREME_PCT_THRESHOLD", 0.20)

    turnover_last = float(df['turnover'].iloc[-1]) if 'turnover' in df.columns else 0.0
    return {
        "score": float(score),
        "turnover": turnover_last,
        "open": float(df['open'].iloc[-1]),
        "is_new_coin": False,
        "is_extreme": bool(is_extreme),
    }