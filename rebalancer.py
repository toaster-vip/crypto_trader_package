import time
from decimal import Decimal, ROUND_DOWN
from config import CONFIG, TRADE
from notifier import send_serverchan_notification
from kucoin_api import KuCoinClient

# 缓存机制
_blacklist = set()
_symbol_buy_cooldown = {}
_price_cache = {}

# 全局参数
TAKE_PROFIT = Decimal(str(TRADE["TAKE_PROFIT"]))  # 止盈
STOP_LOSS = Decimal(str(TRADE["STOP_LOSS"]))      # 止损
MAX_ALLOC_PER_SYMBOL = Decimal("0.10")            # 单币最大投入比例
COOLDOWN_AFTER_LOSS = 3                           # 止损冷却期
USDT_STEP = Decimal("0.01")

# 实时价格获取封装 + 缓存 + 限速重试
def get_price_with_cache(symbol, api_client):
    if symbol in _price_cache:
        return _price_cache[symbol]
    for attempt in range(3):
        try:
            price = api_client.get_symbol_price(symbol)
            _price_cache[symbol] = Decimal(str(price))
            return _price_cache[symbol]
        except Exception as e:
            if "429" in str(e):
                wait = 2 ** attempt
                print(f"[限速] KuCoin 429 错误，等待 {wait}s 重试 {symbol}")
                time.sleep(wait)
            else:
                print(f"[错误] 获取价格失败 {symbol}：{e}")
                break
    return None

def rebalance_portfolio(top_symbols, balances, positions, place_order):
    print("\n🔁 [调仓] 开始执行智能调仓逻辑")

    api = KuCoinClient()
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
        current_price = get_price_with_cache(symbol, api)

        if not current_price or not entry:
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

    # === 买入逻辑 ===
    if not is_simulate:
        usdt_avail = Decimal(str(balances.get("USDT", 0)))
    if usdt_avail <= 1:
        print(f"[调仓] 💰 USDT 余额不足（{usdt_avail}），停止买入")
        return

    max_alloc = (usdt_total * MAX_ALLOC_PER_SYMBOL).quantize(USDT_STEP, rounding=ROUND_DOWN)
    buy_count = 0

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
        if buy_amount < Decimal("5"):
            print(f"[调仓] ⚠️ 资金不足跳过 {symbol}")
            continue

        result = place_order("buy", symbol, float(buy_amount), None, now_time=now)
        if result:
            print(f"[调仓] ✅ 买入 {symbol} 成功，金额 {buy_amount}")
            usdt_avail -= buy_amount
            buy_count += 1
        else:
            print(f"[调仓] ❌ 买入 {symbol} 失败")

        if usdt_avail < Decimal("5"):
            print(f"[调仓] 💸 余额耗尽，结束买入")
            break

    # 冷却期更新
    for s in list(_symbol_buy_cooldown.keys()):
        _symbol_buy_cooldown[s] -= 1
        if _symbol_buy_cooldown[s] <= 0:
            del _symbol_buy_cooldown[s]

    print(f"[调仓] ✅ 调仓结束，共买入 {buy_count} 个币种")


# === 外部接口 ===

def get_blacklist():
    return _blacklist

def is_symbol_in_cooldown(symbol):
    return _symbol_buy_cooldown.get(symbol, 0) > 0