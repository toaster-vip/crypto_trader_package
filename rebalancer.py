import time
from config import CONFIG, LOG_DIR, TRADE, STRATEGY

if CONFIG["SIMULATE"]:
    from sim_account import (
        sim_get_balance as get_account_balances,
        sim_get_positions as get_positions,
        sim_place_order as place_order,
    )
else:
    from kucoin_api import (
        get_trade_account_balances as get_account_balances,
        get_positions,   # 如kucoin_api无get_positions，可自行处理
        place_order,
    )

def rebalance_portfolio(top_symbols, balances, positions, place_order):
    """
    调仓核心逻辑：
    1. 检查当前持仓
    2. 卖出触发止损/调仓的币
    3. 买入推荐新币
    4. 全流程兼容本地模拟和实盘
    """
    # === 止损与调仓卖出 ===
    sell_list = []
    for symbol, pos in positions.items():
        # 检查是否还在top推荐
        if symbol not in top_symbols:
            print(f"[调仓] {symbol} 不在推荐池，准备卖出")
            sell_list.append(symbol)
        # 止损判断等逻辑可自定义加入

    # 卖出
    for symbol in sell_list:
        pos = positions[symbol]
        current_price = 1  # 这里你应该加入最新价格逻辑
        result = place_order("sell", symbol, pos["amount"], current_price, now_time=time.strftime('%Y-%m-%d %H:%M:%S'))
        if result:
            print(f"[调仓] 卖出 {symbol} {pos['amount']} 成功")
        else:
            print(f"[调仓] 卖出 {symbol} 失败")

    # === 买入新币（示例只买第一个）===
    buy_symbol = top_symbols[0] if top_symbols else None
    if buy_symbol:
        usdt_balance = balances.get("USDT", 0)
        amount_to_buy = usdt_balance / 2 / 1  # 1为买入价，这里请补全你的实际价格
        result = place_order("buy", buy_symbol, amount_to_buy, 1, now_time=time.strftime('%Y-%m-%d %H:%M:%S'))
        if result:
            print(f"[调仓] 买入 {buy_symbol} {amount_to_buy} 成功")
        else:
            print(f"[调仓] 买入 {buy_symbol} 失败")