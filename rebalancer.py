# rebalancer.py
from api import client
from strategy import should_sell, check_take_profit_stop_loss
from notifier import send_notification
from config import CONFIG

def rebalance_portfolio(recommended_symbols):
    """
    执行调仓逻辑：卖出不推荐的币种，买入新推荐的币种
    recommended_symbols 是推荐的 symbol 字符串列表，例如 ['BTC_USDT', 'ETH_USDT']
    """
    print("🔁 开始执行自动调仓...")
    holdings = client.get_account_holdings()  # 返回格式 [{'symbol': 'BTC', 'balance': 0.1}, ...]

    symbols_to_sell = []
    symbols_to_keep = set(s.split("_")[0] for s in recommended_symbols)  # 只保留币种前缀如 BTC

    for asset in holdings:
        symbol = asset['symbol']
        balance = asset['balance']

        if symbol not in symbols_to_keep:
            symbols_to_sell.append(symbol)
        else:
            # 止盈止损判断
            price = client.get_symbol_price(f"{symbol}_USDT")
            if check_take_profit_stop_loss(symbol, price):
                symbols_to_sell.append(symbol)

    for symbol in symbols_to_sell:
        result = client.place_order(symbol=f"{symbol}_USDT", side="SELL", amount="ALL")
        if result:
            print(f"🔻 卖出 {symbol}")
            send_notification(f"已卖出 {symbol}")
        else:
            print(f"[ERROR] 卖出 {symbol} 失败")

    # 资金检查
    usdt_balance = client.get_symbol_balance("USDT")
    if usdt_balance < 1:
        print("⚠️ USDT 余额不足，无法买入推荐币种")
        return

    # 买入推荐
    budget = usdt_balance / len(recommended_symbols)
    for symbol in recommended_symbols:
        base = symbol.split("_")[0]
        result = client.place_order(symbol=symbol, side="BUY", amount=budget)
        if result:
            print(f"🟢 买入 {symbol}：{budget} USDT")
            send_notification(f"已买入 {symbol}：{budget} USDT")
        else:
            print(f"[ERROR] 买入 {symbol} 失败")