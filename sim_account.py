import os
import json
from decimal import Decimal, ROUND_DOWN
from config import CONFIG, LOG_DIR

SIM_BALANCE_FILE = os.path.join(LOG_DIR, "balance_sim.json")
SIM_POSITION_FILE = os.path.join(LOG_DIR, "positions_sim.json")
SIM_LOG_FILE = os.path.join(LOG_DIR, "orders_sim.log")

FEE_RATE = Decimal(str(CONFIG["FEE"]["TAKER"]))
START_BALANCE = Decimal(str(CONFIG.get("SIM_START_BALANCE", 10000)))

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
    """首次运行初始化虚拟资金和持仓"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    if not os.path.exists(SIM_BALANCE_FILE):
        save_json(SIM_BALANCE_FILE, {"USDT": float(START_BALANCE)})
    if not os.path.exists(SIM_POSITION_FILE):
        save_json(SIM_POSITION_FILE, {})

def sim_get_balance():
    """返回所有币种当前余额（dict: 币名->数量, USDT包含未用余额）"""
    sim_init()
    return load_json(SIM_BALANCE_FILE, {"USDT": float(START_BALANCE)})

def sim_get_positions():
    """返回当前虚拟持仓，结构: symbol -> {'amount':..., 'entry_price':..., 'last_update':...}"""
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

def sim_place_order(side, symbol, amount, price, now_time=None):
    """
    side: "buy" or "sell"
    symbol: 例如"BTC-USDT"
    amount: 买入是币数量，卖出是币数量
    price: 下单成交价格
    now_time: 可传入字符串时间戳/时间
    返回实际成交明细或None
    """
    balances = sim_get_balance()
    positions = sim_get_positions()
    base, quote = symbol.split("-")
    amount = Decimal(str(amount))
    price = Decimal(str(price))
    fee = Decimal("0")
    total = Decimal("0")
    time_str = now_time or "now"

    if side == "buy":
        # 买入前检查USDT余额
        cost = (amount * price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee = (cost * FEE_RATE).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        total = cost + fee
        if Decimal(str(balances.get("USDT", 0))) < total:
            print(f"[SIM] USDT不足，买入失败: 需{total}, 余额{balances.get('USDT', 0)}")
            return None
        # 更新余额和持仓
        balances["USDT"] = float(Decimal(str(balances["USDT"])) - total)
        positions.setdefault(symbol, {"amount": 0, "entry_price": 0, "last_update": time_str})
        prev_amt = Decimal(str(positions[symbol]["amount"]))
        # 新均价法更新持仓成本
        new_amt = prev_amt + amount
        new_cost = (prev_amt * Decimal(str(positions[symbol]["entry_price"])) + cost) / new_amt if new_amt > 0 else Decimal("0")
        positions[symbol]["amount"] = float(new_amt)
        positions[symbol]["entry_price"] = float(new_cost)
        positions[symbol]["last_update"] = time_str
        sim_log_order("buy", symbol, float(amount), float(price), float(fee), float(total), time_str)

    elif side == "sell":
        # 卖出前检查币余额
        prev_amt = Decimal(str(positions.get(symbol, {}).get("amount", 0)))
        if prev_amt < amount:
            print(f"[SIM] {symbol} 持仓不足，卖出失败: 要卖{amount}, 持有{prev_amt}")
            return None
        gain = (amount * price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        fee = (gain * FEE_RATE).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
        net = gain - fee
        # 更新持仓和余额
        new_amt = prev_amt - amount
        positions[symbol]["amount"] = float(new_amt)
        positions[symbol]["last_update"] = time_str
        balances["USDT"] = float(Decimal(str(balances.get("USDT", 0))) + net)
        if new_amt == 0:
            positions.pop(symbol)
        sim_log_order("sell", symbol, float(amount), float(price), float(fee), float(net), time_str)

    sim_update_balance(balances)
    sim_update_positions(positions)
    return {
        "side": side,
        "symbol": symbol,
        "amount": float(amount),
        "price": float(price),
        "fee": float(fee),
        "total": float(total if side == "buy" else net),
        "time": time_str
    }