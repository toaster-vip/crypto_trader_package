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

# ====== 4h 同频过滤参数（从 config 接入，可动态放宽）======
USE_4H_FILTER            = bool(_cfg("USE_4H_FILTER", True))
MIN_PCT_4H               = float(_cfg("MIN_PCT_4H", 0.005))     # +0.5%
EMA_WINDOW_1H            = int(_cfg("EMA_WINDOW_1H", 6))        # 近6小时 EMA
REQUIRE_LAST1H_ABOVE_EMA = bool(_cfg("REQUIRE_LAST1H_ABOVE_EMA", True))
MIN_VOL_FACTOR           = float(_cfg("MIN_VOL_FACTOR", 1.1))   # 近6根/全样本均量
RELAX_ON_FEW             = bool(_cfg("RELAX_ON_FEW", True))
RELAX_FACTOR             = float(_cfg("RELAX_FACTOR", 0.8))     # 阈值一次性放宽比例
AUTO_RELAX_ENABLED       = bool(_cfg("AUTO_RELAX_ENABLED", True))
AUTO_RELAX_MIN_CAND      = int(_cfg("AUTO_RELAX_MIN_CAND", 6))
AUTO_RELAX_STEPS         = list(_cfg("AUTO_RELAX_STEPS", []))
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

def _hard_filter_batch(api, symbols, pct4h, volf, require_ema):
    """批量执行 4h 硬过滤并返回通过列表"""
    out = [s for s in symbols if _passes_4h_filter(api, s, pct4h, volf, require_ema)]
    log_debug(f"[4h过滤] 阈值 pct4h>={pct4h:.4f}, volf>={volf:.2f}, requireEMA={require_ema} -> 通过 {len(out)}/{len(symbols)}")
    return out

def get_top_gainers_and_volume(api, top_n=None, exclude_symbols=None, market_ok=True):
    """
    生成 USDT 热门候选币列表：
      - 24h 涨幅 & 成交额双因子
      - 4h 同频硬过滤（可关）
      - 候选不足：先单次放宽（RELAX_FACTOR），再按 AUTO_RELAX_STEPS 逐级放宽；
        同时把 CONFIG['MIN_TURNOVER_1H'] 写成更低的门槛，配合 main_trader 的成交额过滤。
    """
    if top_n is None:
        top_n = int(_cfg("HOT_TOP_N", 20))

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
        candidates = list(dict.fromkeys(gainers_24h + vol_top))[:top_n]

    # 市况差时：先把“4h上行”的放在前面（优先而非硬性必须）
    if not market_ok and candidates:
        strict, relax = [], []
        for s in candidates:
            df = api.get_klines(s, '1hour', 8)
            if df is None or len(df) < 4:
                relax.append(s); continue
            open_4h = float(df['open'].iloc[-4])
            close_now = float(df['close'].iloc[-1])
            (strict if close_now > open_4h else relax).append(s)
        candidates = (strict + [x for x in relax if x not in strict])[:max(top_n, _cfg("TOP_N", 2))]

    # —— 4h 同频硬过滤（可开关）——
    filtered = [s for s in candidates if s not in exclude_symbols]
    if USE_4H_FILTER and filtered:
        pct4h_thresh = MIN_PCT_4H
        volf_thresh  = MIN_VOL_FACTOR
        require_ema  = REQUIRE_LAST1H_ABOVE_EMA

        hard = _hard_filter_batch(api, filtered, pct4h_thresh, volf_thresh, require_ema)

        # 第一层：候选太少，按 RELAX_FACTOR 整体放宽一次
        min_need = max(int(_cfg("TOP_N", 2)), max(1, top_n // 4))
        if RELAX_ON_FEW and len(hard) < min_need:
            hard_relaxed = _hard_filter_batch(
                api,
                filtered,
                pct4h_thresh * RELAX_FACTOR,
                volf_thresh  * RELAX_FACTOR,
                require_ema
            )
            seen = set(hard)
            hard = hard + [s for s in hard_relaxed if s not in seen]
            log_debug(f"[4h放宽一次] 数量 {len(hard)} / 目标至少 {min_need}")

        # 第二层：启用阶梯式动态放宽（并同步降低 MIN_TURNOVER_1H，供 main_trader 使用）
        if AUTO_RELAX_ENABLED and len(hard) < max(AUTO_RELAX_MIN_CAND, min_need) and AUTO_RELAX_STEPS:
            for i, step in enumerate(AUTO_RELAX_STEPS, 1):
                pct_mul  = float(step.get("MIN_PCT_4H_MUL", 1.0))
                vol_mul  = float(step.get("MIN_VOL_FACTOR_MUL", 1.0))
                req_ema  = bool(step.get("REQUIRE_EMA", require_ema))
                hard2 = _hard_filter_batch(
                    api,
                    filtered,
                    pct4h_thresh * pct_mul,
                    volf_thresh  * vol_mul,
                    req_ema
                )
                # 合并
                seen = set(hard)
                hard = hard + [s for s in hard2 if s not in seen]
                # 同步成交额门槛（影响后续 scoring 阶段过滤）
                new_turnover = int(step.get("MIN_TURNOVER_1H_ABS", _cfg("MIN_TURNOVER_1H", 40000)))
                if new_turnover < _cfg("MIN_TURNOVER_1H", 40000):
                    CONFIG["MIN_TURNOVER_1H"] = new_turnover
                log_debug(f"[动态放宽 step{i}] cand={len(hard)} / 目标>= {max(AUTO_RELAX_MIN_CAND, min_need)}; MIN_TURNOVER_1H→{CONFIG['MIN_TURNOVER_1H']}")
                if len(hard) >= max(AUTO_RELAX_MIN_CAND, min_need):
                    break

        filtered = hard

    # 退火兜底：仍不足则扩大候选池（成交额、涨幅各加一档），避免选不出
    need = max(int(_cfg("TOP_N", 2)), 1)
    if len(filtered) < need:
        vol_more = [s for s, _ in sorted(usdt_tickers.items(),
                                         key=lambda x: float(x[1].get('volValue', 0.0)),
                                         reverse=True) if s not in exclude_symbols]
        gain_more = [s for s, _ in sorted(usdt_tickers.items(),
                                          key=lambda x: float(x[1].get('changeRate', 0.0)),
                                          reverse=True) if s not in exclude_symbols]
        merged = list(dict.fromkeys(filtered + vol_more[:2*top_n] + gain_more[:2*top_n]))
        filtered = merged

    # 最终裁剪
    final_n = max(need, top_n)
    out = filtered[:final_n]

    log_debug(f"热点候选池({len(out)}): {out[:10]}{' ...' if len(out)>10 else ''}")
    return out

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