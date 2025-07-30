# rebalancer.py

from config import CONFIG
from colorama import Fore, Style
import json
import os
import time

def rebalance_portfolio(client, current_holdings, recommended_symbols, positions_file):
    simulate = CONFIG["SIMULATE"]
    fee_rate = 0.001
    take_profit = CONFIG["TRADE"]["TAKE_PROFIT"]
    stop_loss = CONFIG["TRADE"]["STOP_LOSS"]

    # 加载已持仓记录
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            positions = json.load(f)
    else:
        positions = {}

    # 止盈/止损判断
    for symbol, info in positions.copy().items():
        if symbol not in current_holdings:
            continue
        full_symbol = f"{symbol}-USDT"
        qty = float(current_holdings[symbol])
        entry_price = info["entry_price"]
        current_price = client.get_symbol_price(full_symbol)
        if not current_price:
            continue
        pnl = (current_price - entry_price) / entry_price

        if pnl >= take_profit:
            print(f"{Fore.MAGENTA}🎯 触发止盈卖出: {symbol} 盈利 {pnl:.2%}{Style.RESET_ALL}")
        elif pnl <= stop_loss:
            print(f"{Fore.RED}🛑 触发止损卖出: {symbol} 亏损 {pnl:.2%}{Style.RESET_ALL}")
        else:
            continue

        if not simulate:
            client.place_order(full_symbol, "sell", size=str(qty))
        positions.pop(symbol, None)

    # 卖出不在推荐列表中的币种
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        if full not in recommended_symbols and symbol in positions:
            print(f"{Fore.LIGHTBLACK_EX}🧹 卖出非推荐币种: {symbol}{Style.RESET_ALL}")
            if not simulate:
                client.place_order(full, "sell", size=str(current_holdings[symbol]))
            positions.pop(symbol, None)

    usdt_balance = current_holdings.get("USDT", 0)
    if usdt_balance <= 0:
        print(f"{Fore.YELLOW}⚠️ USDT 余额不足，跳过买入操作{Style.RESET_ALL}")
        with open(positions_file, "w") as f:
            json.dump(positions, f, indent=2)
        return

    # 评分加权分配资金
    weights = {}
    total_score = 0
    for full_symbol in recommended_symbols:
        score = get_score_from_symbol(full_symbol)  # 从符号中获取评分
        weights[full_symbol] = score
        total_score += score

    # 买入推荐币种
    for full_symbol in recommended_symbols:
        base = full_symbol.replace("-USDT", "")
        if base in current_holdings:
            continue  # 已持有

        price = client.get_symbol_price(full_symbol)
        if not price:
            continue

        weight = weights.get(full_symbol, 0)
        allocation = (weight / total_score) * usdt_balance
        qty = round((allocation * (1 - fee_rate)) / price, 4)

        if qty <= 0:
            continue

        print(f"{Fore.GREEN}💚 买入 {base}: 分配 {allocation:.2f} USDT, 数量 {qty}{Style.RESET_ALL}")
        if not simulate:
            client.place_order(full_symbol, "buy", size=str(qty))

        positions[base] = {
            "entry_price": round(price * (1 + fee_rate), 6),
            "timestamp": client.get_timestamp()
        }

    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)

def get_score_from_symbol(symbol):
    # 示例评分提取逻辑，可根据实际情况替换为更准确来源
    # 推荐格式 symbol = "BTC-USDT|0.81"，含评分
    if "|" in symbol:
        try:
            return float(symbol.split("|")[1])
        except:
            return 1.0
    return 1.0