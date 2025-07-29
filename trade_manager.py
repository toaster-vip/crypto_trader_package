# trade_manager.py
import os
from datetime import datetime
from config import TAKE_PROFIT, STOP_LOSS, IS_REAL_TRADING, LOG_DIR, SERVER_CHAN_KEY
from api import client
from notifier import send_wechat_message
from strategy import get_symbol_score

entry_prices = {}  # 内存持仓价格缓存

def get_entry_price(symbol):
    return entry_prices.get(symbol)

def update_entry_price(symbol, price):
    entry_prices[symbol] = price

def log(msg, level="INFO"):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{level}] {msg}")
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        with open(os.path.join(LOG_DIR, f"trade_{datetime.now().date()}.log"), "a") as f:
            f.write(f"[{now}] {level} {msg}\n")
    except Exception as e:
        print(f"[ERROR] 写入日志失败: {e}")

def check_tp_sl(symbol, current_price):
    entry = get_entry_price(symbol)
    if not entry:
        return None
    change = (current_price - entry) / entry
    if change >= TAKE_PROFIT:
        return "TP"
    elif change <= STOP_LOSS:
        return "SL"
    return None

def execute_trade(symbol, side, amount):
    log(f"执行交易：{side} {amount} {symbol}", "TRADE")
    print_color = "\033[92m" if side == "BUY" else "\033[91m"
    print(f"{print_color}📈 {side} {amount} {symbol} \033[0m")

    if not IS_REAL_TRADING:
        log(f"🧪 模拟交易：{side} {amount} {symbol}")
        if side == "BUY":
            update_entry_price(symbol, client.get_symbol_price(symbol))
        return

    resp = client.create_order(symbol=symbol, side=side, amount=amount)
    if resp:
        price = client.get_symbol_price(symbol)
        if side == "BUY":
            update_entry_price(symbol, price)
        notify_msg = f"✅ 成交：{side} {amount} {symbol} @ {price}"
        send_wechat_message(notify_msg)
        log(notify_msg, "SUCCESS")
    else:
        msg = f"❌ 下单失败：{side} {amount} {symbol}"
        send_wechat_message(msg)
        log(msg, "ERROR")

def maybe_sell_if_tp_sl(symbol):
    price = client.get_symbol_price(symbol)
    decision = check_tp_sl(symbol, price)
    if decision:
        reason = "止盈" if decision == "TP" else "止损"
        log(f"⚠️ 触发{reason}，准备卖出：{symbol} 当前价: {price}")
        execute_trade(symbol, "SELL", amount="ALL")  # 假设为市价全部卖出

def maybe_buy(symbol):
    score = get_symbol_score(symbol)
    if score >= 0.7:
        log(f"👍 策略判断可以买入：{symbol}，评分 {score}")
        execute_trade(symbol, "BUY", amount=100)  # 示例买入等额

def maybe_sell_due_to_score(symbol):
    score = get_symbol_score(symbol)
    if score <= 0.3:
        log(f"⚠️ 策略评分过低，准备卖出：{symbol}，评分 {score}")
        execute_trade(symbol, "SELL", amount="ALL")