# rebalancer.py
from config import CONFIG
from notifier import send_serverchan_notification
from colorama import Fore, Style

def rebalance_portfolio(client, current_holdings, recommended_symbols):
    simulate = CONFIG["SIMULATE"]
    take_profit = CONFIG["TRADE"]["TAKE_PROFIT"]
    stop_loss = CONFIG["TRADE"]["STOP_LOSS"]

    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full_symbol = f"{symbol}-USDT"
        if full_symbol not in recommended_symbols:
            print(f"{Fore.RED}💔 卖出弱势币种: {symbol}{Style.RESET_ALL}")
            if not simulate:
                client.place_order(full_symbol, "sell", size="100")  # 此处应使用真实 size 逻辑
            send_serverchan_notification(f"卖出 {symbol}", f"{symbol} 不在推荐列表中，已卖出")

    for full_symbol in recommended_symbols:
        base = full_symbol.replace("-USDT", "")
        if base not in current_holdings:
            print(f"{Fore.GREEN}💚 买入潜力币: {base}{Style.RESET_ALL}")
            if not simulate:
                client.place_order(full_symbol, "buy", size="10")  # 示例：使用固定 size
            send_serverchan_notification(f"买入 {base}", f"{base} 为推荐币种，已买入")