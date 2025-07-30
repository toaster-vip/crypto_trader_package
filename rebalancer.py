from config import CONFIG
from colorama import Fore, Style
import json
import os

def rebalance_portfolio(client, current_holdings, recommended_symbols, positions_file):
    simulate = CONFIG["SIMULATE"]
    fee_rate = 0.001  # 交易手续费

    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            positions = json.load(f)
    else:
        positions = {}

    # 卖出当前持仓中不在推荐列表中的币种
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        if full not in recommended_symbols:
            print(f"{Fore.RED}💔 卖出弱势币种: {symbol}{Style.RESET_ALL}")
            if not simulate:
                client.place_order(full, "sell", size="100")  # 卖出示意，实际系统会处理数量
            positions.pop(symbol, None)

    # 买入推荐但尚未持仓的币种
    for full_symbol in recommended_symbols:
        base = full_symbol.replace("-USDT", "")
        if base not in current_holdings:
            print(f"{Fore.GREEN}💚 买入潜力币: {base}{Style.RESET_ALL}")
            price = client.get_symbol_price(full_symbol)
            if not price:
                continue
            cost = price * (1 + fee_rate)
            if not simulate:
                client.place_order(full_symbol, "buy", size="10")
            positions[base] = {
                "entry_price": round(cost, 6),
                "timestamp": client.get_timestamp()
            }

    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)