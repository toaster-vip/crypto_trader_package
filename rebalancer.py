from config import CONFIG
from colorama import Fore, Style
import json
import os

def rebalance_portfolio(client, current_holdings, recommended_symbols, positions_file):
    simulate = CONFIG["SIMULATE"]
    fee_rate = 0.001  # 手续费 0.1%
    take_profit = CONFIG["TRADE"].get("TAKE_PROFIT", 0.045)
    stop_loss = CONFIG["TRADE"].get("STOP_LOSS", -0.025)

    # 加载本地持仓记录
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            positions = json.load(f)
    else:
        positions = {}

    # 遍历当前持仓（非推荐币 或 触发止盈/止损）
    for symbol in list(current_holdings.keys()):
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        qty = float(current_holdings[symbol])
        should_sell = False

        if symbol in positions:
            entry_price = positions[symbol]["entry_price"]
            current_price = client.get_symbol_price(full)
            if not current_price:
                continue
            pnl = (current_price - entry_price) / entry_price
            if pnl >= take_profit:
                print(f"{Fore.MAGENTA}🎯 止盈卖出: {symbol} 盈利 {pnl:.2%}{Style.RESET_ALL}")
                should_sell = True
            elif pnl <= stop_loss:
                print(f"{Fore.MAGENTA}⛔ 止损卖出: {symbol} 亏损 {pnl:.2%}{Style.RESET_ALL}")
                should_sell = True
        else:
            # 本地无记录但不是推荐币，也卖出
            should_sell = True

        if full not in recommended_symbols:
            print(f"{Fore.RED}💔 卖出弱势币种: {symbol}{Style.RESET_ALL}")
            should_sell = True

        if should_sell:
            if not simulate:
                client.place_order(full, "sell", size=qty)
            positions.pop(symbol, None)

    # 买入推荐币种
    for full_symbol in recommended_symbols:
        base = full_symbol.replace("-USDT", "")
        if base not in current_holdings:
            print(f"{Fore.GREEN}💚 买入潜力币: {base}{Style.RESET_ALL}")
            price = client.get_symbol_price(full_symbol)
            if not price:
                continue
            cost = price * (1 + fee_rate)
            if not simulate:
                client.place_order(full_symbol, "buy", size="10")  # 实际下单数量可调
            positions[base] = {
                "entry_price": round(cost, 6),
                "timestamp": client.get_timestamp()
            }

    # 更新本地持仓记录
    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)