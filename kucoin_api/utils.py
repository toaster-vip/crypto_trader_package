def safe_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

def to_symbol_pair(symbol):
    s = symbol.upper()
    if "-" in s:
        return s
    if not s.endswith("USDT"):
        return f"{s}-USDT"
    return s