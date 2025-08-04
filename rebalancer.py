import time
from decimal import Decimal, ROUND_DOWN
from config import CONFIG, TRADE

from notifier import send_serverchan_notification
from kucoin_api import KuCoinClient
from trade_logger import log_trade, log_rebalance

_blacklist = set()
_symbol_buy_cooldown = {}

TAKE_PROFIT = Decimal(str(TRADE["TAKE_PROFIT"]))
STOP_LOSS = Decimal(str(TRADE["STOP_LOSS"]))
MAX_ALLOC_PER_SYMBOL = Decimal(str(CONFIG.get("MAX_POSITION_RATIO", 0.10)))
COOLDOWN_AFTER_LOSS = int(CONFIG.get("COOLDOWN_AFTER_LOSS", 3))
USDT_STEP = Decimal(str(CONFIG.get("USDT_STEP", 0.01)))
TRAILING_STOP_PCT = Decimal(str(CONFIG.get("TRAILING_STOP_PCT", 0.03)))
MIN_BUY_AMOUNT = Decimal(str(CONFIG.get("MIN_BUY_AMOUNT", 5)))
DRY_RUN = CONFIG.get("DRY_RUN", False)

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
    """
    智能调仓核心逻辑，支持：
      - 固定止盈止损
      - 移动止损和动态基准价刷新
      - 仓位黑名单与冷却
      - 日志记录
      - 低资金自动停止买入
      - DRY_RUN 支持
    """
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
        if not cur_price or cur_price <= 0:
            cur_price = entry
        value = cur_price * amount
        pnl_pct = ((value - cost) / cost * 100) if cost > 0 else Decimal("0")
        print(f" - {symbol:>12}: 持仓 {amount:.4f}，买入成本 {cost:.2f}，现价市值 {value:.2f}，盈亏 {pnl_pct:.2f}%")
        hold_total_cost += cost
        hold_total_value += value
    print(f"📊 持仓总成本: {hold_total_cost:.2f}，现价总市值: {hold_total_value:.2f}，盈亏 {((hold_total_value-hold_total_cost)/hold_total_cost*100) if hold_total_cost else 0:.2f}%\n")

    sell_list = []
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    # === 卖出逻辑 ===
    for symbol, pos in positions.items():
        try:
            amount = Decimal(str(pos.get("amount", 0)))
            base_price = Decimal(str(pos.get("base_price", pos.get("entry_price", "0"))))
            max_price = Decimal(str(pos.get("max_price", base_price)))
        except Exception as e:
            print(f"[异常] 解析持仓数据失败 {symbol}: {e}")
            continue

        current_price = get_price_with_map(symbol, price_map, api)
        if base_price <= 0 or current_price is None or current_price <= 0:
            continue

        if current_price > max_price:
            max_price = current_price
            base_price = max_price
            pos["base_price"] = str(base_price)
            pos["max_price"] = str(max_price)

        pnl_pct = (current_price - base_price) / base_price
        trailing_stop_price = max_price * (Decimal("1") - TRAILING_STOP_PCT)
        reason = ""

        if pnl_pct >= TAKE_PROFIT:
            print(f"✅ 止盈：卖出 {symbol} 盈利 +{pnl_pct:.2%}")
            sell_list.append(symbol)
            reason = "TAKE_PROFIT"
        elif pnl_pct <= STOP_LOSS or current_price <= trailing_stop_price:
            print(f"⛔ 止损：卖出 {symbol} 亏损 {pnl_pct:.2%}（当前价：{current_price}，移动止损价：{trailing_stop_price}）")
            sell_list.append(symbol)
            _symbol_buy_cooldown[symbol] = COOLDOWN_AFTER_LOSS
            _blacklist.add(symbol)
            reason = "STOP_LOSS"
        elif symbol not in top_symbols:
            print(f"📉 排名跌出Top：卖出 {symbol}")
            sell_list.append(symbol)
            reason = "DROPPED_TOP"

        if symbol in sell_list:
            log_trade({
                "timestamp": now,
                "type": "sell",
                "symbol": symbol,
                "amount": float(amount),
                "base_price": float(base_price),
                "current_price": float(current_price or 0),
                "pnl_pct": float(pnl_pct),
                "reason": reason
            })

    # === 执行卖出 ===
    for symbol in sell_list:
        pos = positions.get(symbol)
        if not pos:
            continue
        if DRY_RUN:
            print(f"[DRY_RUN] Would SELL {symbol} amount={pos['amount']}")
            result = {"side": "sell", "symbol": symbol, "amount": pos["amount"], "dry_run": True}
        else:
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
        if not cur_price or cur_price <= 0:
            cur_price = Decimal(str(pos.get("entry_price", 0)))
        hold_total_value += cur_price * Decimal(str(pos.get("amount", 0)))
    print(f"  - 持仓币种市值合计: {hold_total_value:.2f}\n")

    if usdt_avail <= MIN_BUY_AMOUNT:
        print(f"[调仓] 💰 USDT 余额不足（{usdt_avail}），停止买入")
        return

    max_alloc = (usdt_total * MAX_ALLOC_PER_SYMBOL).quantize(USDT_STEP, rounding=ROUND_DOWN)
    buy_count = 0

    # === 买入逻辑 ===
    for symbol in top_symbols:
        if symbol in positions:
            print(f"[调仓] 🟡 已持有 {symbol}，跳过")
            continue
        if symbol in _blacklist:
            print(f"[调仓] ⛔ 黑名单跳过 {symbol}")
            continue
        if _symbol_buy_cooldown.get(symbol, 0) > 0:
            print(f"[调仓] ⏳ 冷却中跳过 {symbol}")
            continue

        buy_amount = min(usdt_avail, max_alloc).quantize(USDT_STEP, rounding=ROUND_DOWN)
        if buy_amount < MIN_BUY_AMOUNT:
            print(f"[调仓] ⚠️ 资金不足跳过 {symbol}")
            continue

        if DRY_RUN:
            print(f"[DRY_RUN] Would BUY {symbol} amount={float(buy_amount)}")
            result = {"side": "buy", "symbol": symbol, "amount": float(buy_amount), "dry_run": True}
            cur_price = get_price_with_map(symbol, price_map, api)
            positions[symbol] = {
                "amount": float(buy_amount / (cur_price or Decimal("1"))),
                "entry_price": float(cur_price or 0),
                "last_update": now,
                "base_price": str(cur_price or 0),
                "max_price": str(cur_price or 0)
            }
        else:
            result = place_order("buy", symbol, float(buy_amount), None, now_time=now)
            cur_price = get_price_with_map(symbol, price_map, api)
            if result and cur_price:
                positions[symbol] = {
                    "amount": float(buy_amount / (cur_price or Decimal("1"))),
                    "entry_price": float(cur_price or 0),
                    "last_update": now,
                    "base_price": str(cur_price or 0),
                    "max_price": str(cur_price or 0)
                }

        if result:
            print(f"[调仓] ✅ 买入 {symbol} 成功，金额 {buy_amount}")
            usdt_avail -= buy_amount
            buy_count += 1

            log_trade({
                "timestamp": now,
                "type": "buy",
                "symbol": symbol,
                "amount": float(buy_amount),
                "price": float(cur_price or 0),
                "reason": "REBALANCE_BUY"
            })
        else:
            print(f"[调仓] ❌ 买入 {symbol} 失败")

        if usdt_avail < MIN_BUY_AMOUNT:
            print(f"[调仓] 💸 余额耗尽，结束买入")
            break

    print("\n[调仓] 买入后账户快照：")
    print(f"  - 可用USDT: {usdt_avail:.2f}")
    print(f"  - 持仓币种市值合计: {hold_total_value:.2f}\n")

    # 冷却期管理
    for s in list(_symbol_buy_cooldown.keys()):
        _symbol_buy_cooldown[s] -= 1
        if _symbol_buy_cooldown[s] <= 0:
            del _symbol_buy_cooldown[s]

    log_rebalance({
        "timestamp": now,
        "top_symbols": top_symbols,
        "buy_count": buy_count,
        "sell_list": sell_list,
        "hold_value": float(hold_total_value),
        "usdt_avail": float(usdt_avail),
    })

    print(f"[调仓] ✅ 调仓结束，共买入 {buy_count} 个币种")

def get_blacklist():
    return _blacklist

def is_symbol_in_cooldown(symbol):
    return _symbol_buy_cooldown.get(symbol, 0) > 0

# ========== 策略风控风险点说明 ==========
# 1. 已持有币如创新高即刷新基准价，可锁定盈利但震荡市下或频繁刷新可能引发“止盈变止损”，需结合移动止损和固定止损双保险。
# 2. 建议日志每轮定期分析频繁止损与盈亏分布，调整触发阈值参数，避免高频交易带来成本和滑点风险。
# 3. 可考虑设“最小基准涨幅”或“连续创新高”后才刷新base_price等策略优化，进一步抑制追高卖低。