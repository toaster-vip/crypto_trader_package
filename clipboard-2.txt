# rebalancer.py
from api import client
from strategy import should_sell, check_take_profit_stop_loss
from notifier import notify
from config import IS_REAL_TRADING
import time

def rebalance_portfolio(top_candidates, max_holdings=3):
    """
    自动调仓逻辑：
    1. 获取当前持仓
    2. 评估哪些应卖出（弱币）
    3. 从推荐中选择未持有的潜力币种
    4. 若 USDT 不足，卖出弱币换仓
    """
    holdings = client.get_account_holdings()
    prices = {}
    for sym in holdings:
        prices[sym] = client.get_symbol_price(sym)

    # 第一步：遍历当前持仓，判断是否需要卖出
    for symbol in holdings:
        current_price = prices.get(symbol)
        if not current_price:
            continue

        sell_reason = None
        score = client.get_symbol_score(symbol)
        if should_sell(symbol, score):
            sell_reason = f"评分过低（{score:.2f}）"
        else:
            trigger = check_take_profit_stop_loss(symbol, current_price)
            if trigger:
                sell_reason = trigger

        if sell_reason:
            print(f"\033[91m🔻 卖出信号触发 {symbol} - 原因: {sell_reason}\033[0m")
            if IS_REAL_TRADING:
                client.place_order(symbol, "sell", quantity="all")
            notify(f"🔻 卖出 {symbol} - 原因: {sell_reason}")
            time.sleep(0.8)

    # 第二步：获取当前持仓后可能释放的资金
    usdt_balance = client.get_currency_balance("USDT")
    print(f"💰 当前可用 USDT：{usdt_balance}")

    # 第三步：买入潜力币（最多 max_holdings 个）
    new_buy = [s for s in top_candidates if s not in holdings][:max_holdings]
    for symbol in new_buy:
        print(f"\033[92m🟢 买入候选币：{symbol}\033[0m")
        if IS_REAL_TRADING:
            client.place_order(symbol, "buy", usdt_amount=usdt_balance / len(new_buy))
        notify(f"🟢 买入新币：{symbol}")
        time.sleep(0.8)