import time
from decimal import Decimal, ROUND_DOWN
from config import CONFIG, TRADE
from notifier import send_serverchan_notification

# 内部缓存：币种黑名单与冷却次数
_blacklist = set()
_symbol_buy_cooldown = {}

# 全局设定
TAKE_PROFIT = Decimal(str(TRADE["TAKE_PROFIT"]))  # 止盈
STOP_LOSS = Decimal(str(TRADE["STOP_LOSS"]))      # 止损
MAX_ALLOC_PER_SYMBOL = Decimal("0.10")            # 单币最大投入比例 = 10%
COOLDOWN_AFTER_LOSS = 3                           # 单币亏损后冷却N轮

# 精度设置
USDT_STEP = Decimal("0.01")

def rebalance_portfolio(top_symbols, balances, positions, place_order):
    print("\n🔁 [调仓] 开始执行智能调仓逻辑")

    is_simulate = CONFIG.get("SIMULATE", True)
    raw_usdt = Decimal(str(balances.get("USDT", 0)))
    usdt_total = Decimal(str(CONFIG.get("USDT_CAP", 100))) if is_simulate else raw_usdt
    usdt_avail = usdt_total

    positions = {k: v for k, v in positions.items() if Decimal(str(v.get("amount", 0))) > 0}
    sell_list = []
    now = time.strftime('%Y-%m-%d %H:%M:%S')

    # === 卖出逻辑 ===
    for symbol, pos in positions.items():
        entry = Decimal(str(pos.get("entry_price", 0)))
        amount = Decimal(str(pos.get("amount", 0)))
        current_price = entry  # ⛳ 如需实时报价可替换此行

        if current_price and entry:
            pnl_pct = (current_price - entry) / entry
            if pnl_pct >= TAKE_PROFIT:
                print(f"✅ 止盈条件满足，准备卖出 {symbol} 盈利 +{pnl_pct:.2%}")
                sell_list.append(symbol)
            elif pnl_pct <= STOP_LOSS:
                print(f"⛔ 止损条件满足，准备卖出 {symbol} 亏损 {pnl_pct:.2%}")
                sell_list.append(symbol)
                _symbol_buy_cooldown[symbol] = COOLDOWN_AFTER_LOSS
                _blacklist.add(symbol)
            elif symbol not in top_symbols:
                print(f"📉 排名跌出Top，准备调仓卖出 {symbol}")
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

    # 更新模拟/实盘后的余额
    if not is_simulate:
        usdt_avail = Decimal(str(balances.get("USDT", 0)))

    if usdt_avail <= 1:
        print(f"[调仓] 💰 USDT 可用余额过低（{usdt_avail}），停止买入")
        return

    max_alloc = (usdt_total * MAX_ALLOC_PER_SYMBOL).quantize(USDT_STEP, rounding=ROUND_DOWN)
    buy_count = 0

    for symbol in top_symbols:
        if symbol in positions:
            print(f"[调仓] 🟡 已持有 {symbol}，跳过重复买入")
            continue
        if symbol in _blacklist:
            print(f"[调仓] ⛔ {symbol} 已加入黑名单，跳过买入")
            continue
        if _symbol_buy_cooldown.get(symbol, 0) > 0:
            print(f"[调仓] ⏳ {symbol} 正在冷却中（剩余 {_symbol_buy_cooldown[symbol]} 轮），跳过")
            continue

        buy_amount = min(usdt_avail, max_alloc).quantize(USDT_STEP, rounding=ROUND_DOWN)
        if buy_amount < Decimal("5"):
            print(f"[调仓] ⚠️ 可分配 {buy_amount} USDT 太少，跳过 {symbol}")
            continue

        result = place_order("buy", symbol, float(buy_amount), None, now_time=now)
        if result:
            print(f"[调仓] ✅ 买入 {symbol} 成功，金额 {buy_amount}")
            usdt_avail -= buy_amount
            buy_count += 1
        else:
            print(f"[调仓] ❌ 买入 {symbol} 失败")

        if usdt_avail < Decimal("5"):
            print(f"[调仓] 💸 USDT 剩余不足，结束买入")
            break

    # 冷却计数更新
    for s in list(_symbol_buy_cooldown.keys()):
        _symbol_buy_cooldown[s] -= 1
        if _symbol_buy_cooldown[s] <= 0:
            del _symbol_buy_cooldown[s]

    print(f"[调仓] 🔚 调仓完毕，共买入 {buy_count} 个币种")