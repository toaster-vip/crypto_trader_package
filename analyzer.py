# analyzer.py
from api import client
from strategy import get_symbol_score
from config import CONFIG
from datetime import datetime
import traceback

def analyze_symbols(candidates):
    """
    针对给定币种列表，计算评分并排序
    """
    result = []
    for symbol in candidates:
        try:
            price = client.get_symbol_price(symbol)
            if price is None:
                continue
            score = get_symbol_score(symbol)
            result.append((symbol, score, price))
        except Exception as e:
            print(f"[ERROR] 分析 {symbol} 失败: {e}")
            traceback.print_exc()
    # 按评分降序排列
    result.sort(key=lambda x: x[1], reverse=True)
    return result

def get_top_symbols(limit=5):
    """
    获取评分最高的前 N 个币种作为候选
    """
    try:
        supported_symbols = client.get_valid_symbols()  # 动态从交易所拉取支持币种
    except Exception as e:
        print(f"[WARN] 获取交易币种失败，使用默认 SYMBOLS 列表")
        supported_symbols = CONFIG.get("SYMBOLS", [])

    analysis_result = analyze_symbols(supported_symbols)
    print(f"🧠 策略分析完成，推荐前 {limit} 个币种：")
    for sym, score, price in analysis_result[:limit]:
        color = "\033[92m" if score >= 0.7 else ("\033[93m" if score >= 0.4 else "\033[90m")
        print(f"{color}{sym}: Score={score:.3f}, Price={price}\033[0m")
    return [sym for sym, _, _ in analysis_result[:limit]]

def find_emerging_tokens():
    """
    识别可能的新上线币种（可选）
    """
    all_symbols = client.get_valid_symbols()
    candidates = [s for s in all_symbols if s.endswith("_USDT") and s.startswith(("B", "E", "T"))]
    result = analyze_symbols(candidates)
    emerging = [s for s, score, _ in result if score >= 0.6]
    print(f"🌱 新币候选：{emerging}")
    return emerging

def analyze_all_symbols(client, symbols):
    """
    主分析函数：分析多个币种并返回评分字典
    """
    scored = {}
    for symbol in symbols:
        score = get_symbol_score(symbol)
        scored[symbol] = score
    return scored 