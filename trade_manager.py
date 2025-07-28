from config import CONFIG
import logging

def execute_trade(symbol, market_data, signal):
    price = float(market_data.get("result", {}).get("data", [{}])[0].get("a", 0))
    if signal == 1:
        action = "BUY"
    elif signal == -1:
        action = "SELL"
    else:
        action = "HOLD"
    if CONFIG["SIMULATE"]:
        logging.info(f"[SIM] {action} {symbol} @ {price}")
    else:
        # place real order (omitted)
        logging.info(f"[REAL] {action} {symbol} @ {price}")