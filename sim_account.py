import os
import json
from decimal import Decimal, ROUND_DOWN
from config import CONFIG, LOG_DIR

SIM_BALANCE_FILE = os.path.join(LOG_DIR, CONFIG.get("SIM_BALANCE_FILE", "balance_sim.json"))
SIM_POSITION_FILE = os.path.join(LOG_DIR, CONFIG.get("SIM_POSITION_FILE", "positions_sim.json"))
SIM_LOG_FILE = os.path.join(LOG_DIR, CONFIG.get("SIM_LOG_FILE", "orders_sim.log"))

FEE_RATE = Decimal(str(CONFIG["FEE_RATE"]))
START_BALANCE = Decimal(str(CONFIG.get("SIM_START_BALANCE", 10000)))
MIN_BUY_AMOUNT = Decimal(str(CONFIG.get("MIN_BUY_AMOUNT", 5)))
SIM_SLIPPAGE_PCT = Decimal(str(CONFIG.get("SIM_SLIPPAGE_PCT", 0)))   # 滑点默认0

def load_json(filepath, default):
    if os.path.exists(filepath):
        try:
            with open(filepath, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"[SIM] 加载{filepath}失败: {e}")
    return default

def save_json(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f, indent=2)

def sim_init():
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    if not os.path.exists(SIM_BALANCE_FILE):
        save_json(SIM_BALANCE_FILE, {"USDT": float(START_BALANCE)})
    if not os.path.exists(SIM_POSITION_FILE):
        save_json(SIM_POSITION_FILE, {})

def sim_get_balance():
    sim_init()
    return load_json(SIM_BALANCE_FILE, {"USDT": float(START_BALANCE)})

def sim_get_positions():
    sim_init()
    return load_json(SIM_POSITION_FILE, {})

def sim_update_balance(balances):
    save_json(SIM_BALANCE_FILE, balances)

def sim_update_positions(positions):
    save_json(SIM_POSITION_FILE, positions)

def sim_log_order(side, symbol, amount, price, fee, total, time_str):
    line = f"{time_str} {side.upper()} {symbol} {amount} @ {price}, fee={fee}, total={total}\n"
    with open(SIM_LOG_FILE, "a") as f:
        f.write(line)

def sim_place_order(side, symbol, amount, price=None, now_time=None, market_price=None):
    balances = sim_get_balance()
    positions = sim_get_positions()
    base, quote = symbol.split("-")
    amount = Decimal(str(amount))
    time_str = now_time or "now"

    # ====== 滑点处理 ======
    final_price = Decimal(str(market_price if market_price else price if price else 1))
    if side == "buy":
        final_price *= (1 + SIM_SLIPPAGE_PCT)
    elif side == "sell":
        final_price *= (1 - SIM_SLIPPAGE_PCT)

    if side == "buy":
        qty = (amount / final_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        cost = (qty * final_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee = (cost * FEE_RATE).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        total = cost + fee
        if Decimal(str(balances.get("USDT", 0))) < total or total < MIN_BUY_AMOUNT:
            print(f"[SIM] USDT不足或金额过小，买入失败: 需{total}, 余额{balances.get('USDT', 0)}")
            return None
        balances["USDT"] = float(Decimal(str(balances["USDT"])) - total)
        positions.setdefault(symbol, {"amount": 0, "entry_price": 0, "last_update": time_str})
        prev_amt = Decimal(str(positions[symbol]["amount"]))
        new_amt = prev_amt + qty
        new_cost = (prev_amt * Decimal(str(positions[symbol]["entry_price"])) + cost) / new_amt if new_amt > 0 else Decimal("0")
        positions[symbol]["amount"] = float(new_amt)
        positions[symbol]["entry_price"] = float(new_cost)
        positions[symbol]["last_update"] = time_str
        sim_log_order("buy", symbol, float(qty), float(final_price), float(fee), float(total), time_str)
        result = {
            "side": side,
            "symbol": symbol,
            "amount": float(qty),
            "price": float(final_price),
            "fee": float(fee),
            "total": float(total),
            "time": time_str
        }
    elif side == "sell":
        prev_amt = Decimal(str(positions.get(symbol, {}).get("amount", 0)))
        if prev_amt < amount:
            print(f"[SIM] {symbol} 持仓不足，卖出失败: 要卖{amount}, 持有{prev_amt}")
            return None
        gain = (amount * final_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee = (gain * FEE_RATE).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        net = gain - fee
        new_amt = prev_amt - amount
        positions[symbol]["amount"] = float(new_amt)
        positions[symbol]["last_update"] = time_str
        balances["USDT"] = float(Decimal(str(balances.get("USDT", 0))) + net)
        if new_amt == 0:
            positions.pop(symbol)
        sim_log_order("sell", symbol, float(amount), float(final_price), float(fee), float(net), time_str)
        result = {
            "side": side,
            "symbol": symbol,
            "amount": float(amount),
            "price": float(final_price),
            "fee": float(fee),
            "total": float(net),
            "time": time_str
        }
    else:
        return None

    sim_update_balance(balances)
    sim_update_positions(positions)
    return result

def sim_reset():
    """重置模拟账户资产和仓位"""
    save_json(SIM_BALANCE_FILE, {"USDT": float(START_BALANCE)})
    save_json(SIM_POSITION_FILE, {})
    open(SIM_LOG_FILE, "w").close()
    print("[SIM] 模拟器已重置。")