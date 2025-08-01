import time
from decimal import Decimal, ROUND_DOWN
from config import CONFIG, TRADE
from notifier import send_serverchan_notification
from kucoin_api import KuCoinClient

_blacklist = set()
_symbol_buy_cooldown = {}

TAKE_PROFIT = Decimal(str(TRADE["TAKE_PROFIT"]))
STOP_LOSS = Decimal(str(TRADE["STOP_LOSS"]))
MAX_ALLOC_PER_SYMBOL = Decimal(str(CONFIG.get("MAX_POSITION_RATIO", 0.18)))
COOLDOWN_AFTER_LOSS = 3
USDT_STEP = Decimal("0.01")

def get_price_with_map(symbol, price_map, api_client):
    if price_map and symbol in price_map and price_map[symbol] is not None:
        return Decimal(str(price_map[symbol]))
    try:
        price = api_client.get_symbol_price(symbol)
        if price:
            return Decimal(str(price))
    except Exception as e:
        print(f"[错误] 获取{symbol}实时价格失败：{e}")
    return None

def rebalance_portfolio(top_symbols, balances, positions, place_order, price_map=None):
    print("\n🔁 [调仓] 开始执行智能调仓逻辑")
    api = KuCoinClient()
    is_simulate = CONFIG.get("SIMULATE", True)
    raw_usdt = Decimal(str(balances.get("USDT", 0)))
    usdt_total = Decimal(str(CONFIG.get("SIM_START_BALANCE", 100))) if is_simulate else raw_usdt
    usdt_avail = raw_usdt

    positions = {k: v for k, v in positions.items() if Decimal(str(v.get("amount", 0))) > 0}
    print("🪙 当前持仓市值与成本：")
    hold_total_cost, hold_total_value = Decimal("0"), Decimal("0")
    for symbol, pos in positions.items():
        entry = Decimal(str(pos.get("entry_price", 0)))
        amount = Decimal(str(pos.get("amount", 0)))
        cost = entry * amount
        cur_price = get_price_with_map(symbol, price_map, api)
        value = (cur_price or Decimal("0")) * amount
        pnl_pct = ((value - cost) / cost * 100) if cost > 0 else Decimal("0")
        print(f" - {symbol:>12}: 持仓 {amount:.4f}，买入成本 {cost:.2f}，现价市值 {value:.2f}，盈亏 {pnl_pct:.2f}%")
        hold_total_cost += cost
        hold_total_value += value
    print(f"📊 持仓总成本: {hold_total_cost:.2f}，现价总市值: {hold_total_value:.2f}，盈亏 {((hold_total_value-hold_total_cost)/hold_total_cost*100) if hold_total_cost else 0:.2f}%\n")

    sell_list = []
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for symbol, pos in positions.items():
        try:
            entry = Decimal(str(pos.get("entry_price", 0)))
            amount = Decimal(str(pos.get("amount", 0)))
        except Exception as e:
            print(f"[异常] 解析持仓数据失败 {symbol}: {e}")
            continue
        current_price = get_price_with_map(symbol, price_map, api)
        if entry is None or entry <= 0:
            continue
        if current_price is None or current_price <= 0:
            continue
        pnl_pct = (current_price - entry) / entry
        if pnl_pct >= TAKE_PROFIT:
            print(f"✅ 止盈：卖出 {symbol} 盈利 +{pnl_pct:.2%}")
            sell_list.append(symbol)
        elif pnl_pct <= STOP_LOSS:
            print(f"⛔ 止损：卖出 {symbol} 亏损 {pnl_pct:.2%}")
            sell_list.append(symbol)
            _symbol_buy_cooldown[symbol] = COOLDOWN_AFTER_LOSS
            _blacklist.add(symbol)
        elif symbol not in top_symbols:
            print(f"📉 排名跌出Top：卖出 {symbol}")
            sell_list.append(symbol)

    for symbol in sell_list:
        pos = positions.get(symbol)
        if not pos:
            continue
        result = place_order("sell", symbol, pos["amount"], None, now_time=now)
        if result:
            print(f"[调仓] ✅ 卖出 {symbol} 成功")
        else:
            print(f"[调仓] ❌ 卖出 {symbol} 失败")

    if not is_simulate:
        usdt_avail = Decimal(str(balances.get("USDT", 0)))
    print("\n[调仓] 卖出后账户快照：")
    print(f"  - 可用USDT: {usdt_avail:.2f}")
    for symbol in sell_list:
        positions.pop(symbol, None)
    hold_total_value = Decimal("0")
    for symbol, pos in positions.items():
        cur_price = get_price_with_map(symbol, price_map, api)
        if cur_price:
            hold_total_value += cur_price * Decimal(str(pos.get("amount", 0)))
    print(f"  - 持仓币种市值合计: {hold_total_value:.2f}\n")

    cur_holding_count = len([s for s in positions if Decimal(str(positions[s].get("amount", 0))) > 0])
    max_hold_count = CONFIG.get("MAX_HOLD_COUNT", 6)
    remain_slots = max_hold_count - cur_holding_count
    reserve_ratio = Decimal(str(CONFIG.get("RESERVE_RATIO", 0.12)))
    min_buy_amount = Decimal(str(CONFIG.get("MIN_BUY_AMOUNT", 5)))
    fixed_buy_amount = Decimal(str(CONFIG.get("FIXED_BUY_AMOUNT", 10)))
    usdt_buyable = (usdt_avail * (Decimal("1") - reserve_ratio)).quantize(USDT_STEP, rounding=ROUND_DOWN)

    buy_count = 0
    for symbol in top_symbols:
        if remain_slots <= 0 or usdt_buyable < min_buy_amount:
            break
        if symbol in positions or symbol in _blacklist or _symbol_buy_cooldown.get(symbol, 0) > 0:
            continue

        max_alloc = (usdt_total * MAX_ALLOC_PER_SYMBOL).quantize(USDT_STEP, rounding=ROUND_DOWN)
        buy_amount = min(usdt_buyable / remain_slots, fixed_buy_amount, max_alloc)
        buy_amount = buy_amount.quantize(USDT_STEP, rounding=ROUND_DOWN)
        if buy_amount < min_buy_amount:
            print(f"[调仓] ⚠️ 资金不足跳过 {symbol}")
            continue

        result = place_order("buy", symbol, float(buy_amount), None, now_time=now)  # PATCH: 只传金额
        if result:
            print(f"[调仓] ✅ 买入 {symbol} 成功，金额 {buy_amount}")
            usdt_buyable -= buy_amount
            buy_count += 1
            remain_slots -= 1
        else:
            print(f"[调仓] ❌ 买入 {symbol} 失败")

        if usdt_buyable < min_buy_amount:
            print(f"[调仓] 💸 余额耗尽，结束买入")
            break

    print("\n[调仓] 买入后账户快照：")
    print(f"  - 可用USDT: {usdt_buyable:.2f}")
    print(f"  - 持仓币种市值合计: {hold_total_value:.2f}\n")

    for s in list(_symbol_buy_cooldown.keys()):
        _symbol_buy_cooldown[s] -= 1
        if _symbol_buy_cooldown[s] <= 0:
            del _symbol_buy_cooldown[s]

    print(f"[调仓] ✅ 调仓结束，共买入 {buy_count} 个币种")

def get_blacklist():
    return _blacklist

def is_symbol_in_cooldown(symbol):
    return _symbol_buy_cooldown.get(symbol, 0) > 0