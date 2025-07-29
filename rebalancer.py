# rebalancer.py

import time
from api import client
from strategy import should_sell, check_take_profit_stop_loss
from notifier import notify
from config import IS_REAL_TRADING

def rebalance_portfolio(top_candidates, max_holdings=3):
    """
    自动调仓逻辑：
    1. 获取当前持仓
    2. 卖出弱币或止盈止损
    3. 买入推荐币种（未持有的前 N 个）
    """
    holdings = client.get_account_holdings()  # [{'symbol': 'BOME', 'balance': 123.0}, ...]
    held_symbols = [h['symbol'] for h in holdings]

    prices = {}
    for h in holdings:
        symbol = h['symbol']
        prices[symbol] = client.get_symbol_price(symbol)

    # 1️⃣ 处理卖出逻辑
    for h in holdings:
        symbol = h['symbol']
        current_price = prices.get(symbol)
        if not current_price:
            print(f"[WARN] 获取 {symbol} 价格失败，跳过卖出判断")
            continue

        score = client.get_symbol_score(symbol)
        reason = None

        if should_sell(symbol, score):
            reason = f"评分过低（{score:.2f}）"
        else:
            reason = check_take_profit_stop_loss(symbol, current_price)

        if reason:
            print(f"\033[91m🔻 卖出信号：{symbol} | 原因：{reason}\033[0m")
            if IS_REAL_TRADING:
                client.place_order(symbol, "sell", quantity="all")
            notify(f"🔻 卖出 {symbol} - 原因：{reason}")
            time.sleep(0.8)

    # 2️⃣ 获取 USDT 余额
    usdt_balance = client.get_currency_balance("USDT")
    print(f"💰 当前可用 USDT：{usdt_balance}")

    # 3️⃣ 筛选还未持有的推荐币
    new_buys = [s for s in top_candidates if s not in held_symbols][:max_holdings]

    if not new_buys:
        print("📭 没有新的买入币种，跳过买入。")
        return

    per_amount = usdt_balance / len(new_buys) if usdt_balance > 0 else 0
    if per_amount <= 0:
        print("⚠️ USDT 不足，无法进行买入操作")
        return

    for symbol in new_buys:
        print(f"\033[92m🟢 准备买入：{symbol}，每币分配 USDT: {per_amount:.2f}\033[0m")
        if IS_REAL_TRADING:
            client.place_order(symbol, "buy", usdt_amount=per_amount)
        notify(f"🟢 买入新币：{symbol}")
        time.sleep(0.8)