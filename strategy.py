import numpy as np
import pandas as pd
from config import CONFIG
from kucoin_api import get_klines, get_supported_symbols

# ========== 单币种各指标打分 ==========

def score_symbol(symbol, kline_data, config=CONFIG):
    # 例子: MACD、RSI、均线、动量、OBV、KDJ、布林带等
    # 你可以按自己项目实际调整和补充
    scores = {}

    if kline_data is None or len(kline_data) < 30:
        # K线数据不足直接最低分
        scores['total'] = -1
        return scores

    closes = np.array([x['close'] for x in kline_data])
    volumes = np.array([x['volume'] for x in kline_data])
    weights = config['STRATEGY']

    # MACD（快慢线差值打分）
    fast = pd.Series(closes).ewm(span=12).mean()
    slow = pd.Series(closes).ewm(span=26).mean()
    macd = fast - slow
    scores['MACD'] = float(macd.iloc[-1]) if len(macd) else 0

    # RSI
    deltas = np.diff(closes)
    up = deltas[deltas > 0].sum() / 14 if np.any(deltas > 0) else 0
    down = -deltas[deltas < 0].sum() / 14 if np.any(deltas < 0) else 0
    rs = up / down if down != 0 else 0
    rsi = 100 - 100 / (1 + rs) if down != 0 else 100
    scores['RSI'] = float(rsi)

    # 均线
    sma20 = closes[-20:].mean() if len(closes) >= 20 else closes.mean()
    sma_score = closes[-1] / sma20 if sma20 != 0 else 1
    scores['SMA'] = float(sma_score)

    # 动量
    momentum = closes[-1] - closes[-10] if len(closes) >= 10 else closes[-1] - closes[0]
    scores['MOMENTUM'] = float(momentum)

    # 趋势/ADX/OBV/KDJ/BOLL等其它指标略，留接口
    # TODO: 可按你原有逻辑补充其它分项

    # 汇总总分（线性加权，例子）
    total_score = (
        weights['MACD_WEIGHT'] * scores.get('MACD', 0) +
        weights['RSI_WEIGHT'] * scores.get('RSI', 0) +
        weights['SMA_WEIGHT'] * scores.get('SMA', 0) +
        weights['MOMENTUM_WEIGHT'] * scores.get('MOMENTUM', 0)
        # ...其它权重继续加
    )
    scores['total'] = float(total_score)
    return scores

# ========== 全部币种打分 ==========

def get_all_scores(symbols=None, config=CONFIG):
    """
    批量获取所有币种评分字典
    返回: {symbol: {各项分数, 'total': ...}}
    """
    if symbols is None:
        symbols = get_supported_symbols()
    all_scores = {}
    for symbol in symbols:
        kline = get_klines(symbol, ktype="15min", limit=100)
        score = score_symbol(symbol, kline, config)
        all_scores[symbol] = score
    return all_scores

# ========== 排序与过滤 ==========

def sort_and_filter_symbols(all_scores, top_n=5, min_score=0):
    """
    按总分降序，选Top N并筛掉低分币
    """
    sorted_syms = sorted(
        [(s, sc['total']) for s, sc in all_scores.items() if sc.get('total', -9) > min_score],
        key=lambda x: x[1],
        reverse=True
    )
    return [s for s, score in sorted_syms[:top_n]]

# ========== 主入口适配函数 ==========

def score_symbols(symbols=None, config=CONFIG, top_n=5, min_score=0):
    """
    主入口：批量评分并输出Top推荐币种
    兼容main_trader.py调用
    """
    all_scores = get_all_scores(symbols, config)
    top_symbols = sort_and_filter_symbols(all_scores, top_n=top_n, min_score=min_score)
    return top_symbols