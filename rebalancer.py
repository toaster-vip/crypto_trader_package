# rebalancer.py

import os
import json
import time
from config import CONFIG
from colorama import Fore, Style

BUY_HISTORY_FILE = os.path.join(CONFIG["LOG_DIR"], "buy_history.json")
HOLD_THRESHOLD_RANK = 10
SCORE_DIFF_THRESHOLD = 0.10  # 新币评分需高出当前币10%
REQUIRE_CONSISTENT_ROUNDS = 2  # 连续出现轮次要求

def rebalance_portfolio(client, current_holdings, recommended_tuples, positions_file):
    simulate = CONFIG["SIMULATE"]
    fee_rate = 0.001
    take_profit = CONFIG["TRADE"]["TAKE_PROFIT"]
    stop_loss = CONFIG["TRADE"]["STOP_LOSS"]

    recommended_symbols = [s for s, _ in recommended_tuples]
    recommended_scores = {s: sc for s, sc in recommended_tuples}
    top_symbols = [s for s, _ in recommended_tuples[:3]]

    # 加载 positions
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            positions = json.load(f)
    else:
        positions = {}

    # 止盈/止损逻辑
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
            print(f"{Fore.MAGENTA}🎯 止盈卖出 {symbol} 盈利 {pnl:.2%}{Style.RESET_ALL}")
        elif pnl <= stop_loss:
            print(f"{Fore.RED}🛑 止损卖出 {symbol} 亏损 {pnl:.2%}{Style.RESET_ALL}")
        else:
            continue
        if not simulate:
            client.place_order(full_symbol, "sell", size=str(qty))
        positions.pop(symbol, None)

    # 卖出不再推荐且不满足“持仓保持权重+评分门槛”的币种
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        if full in recommended_symbols:
            rank = recommended_symbols.index(full) + 1
            if rank <= HOLD_THRESHOLD_RANK:
                continue  # 保持持仓权重
            recommended_score = recommended_scores.get(full, 0)
            current_score = recommended_scores.get(full, 0)
            min_required = max(recommended_scores.values()) * (1 - SCORE_DIFF_THRESHOLD)
            if current_score >= min_required:
                continue  # 差距不够大，不卖
        if symbol in positions:
            print(f"{Fore.LIGHTBLACK_EX}🧹 卖出非优先币种 {symbol}{Style.RESET_ALL}")
            if not simulate:
                client.place_order(full, "sell", size=str(current_holdings[symbol]))
            positions.pop(symbol, None)

    usdt_balance = current_holdings.get("USDT", 0)
    if usdt_balance <= 0:
        print(f"{Fore.YELLOW}⚠️ USDT 余额不足，跳过买入操作{Style.RESET_ALL}")
        with open(positions_file, "w") as f:
            json.dump(positions, f, indent=2)
        return

    # 加载买入历史
    if os.path.exists(BUY_HISTORY_FILE):
        with open(BUY_HISTORY_FILE, "r") as f:
            buy_history = json.load(f)
    else:
        buy_history = {}

    # 更新连续入榜轮数
    for s, _ in recommended_tuples:
        buy_history[s] = buy_history.get(s, 0) + 1
    for s in list(buy_history):
        if s not in recommended_symbols:
            buy_history[s] = 0

    # 动态评分加权分配资金
    total_score = sum([recommended_scores[s] for s in top_symbols])
    for s in top_symbols:
        base = s.replace("-USDT", "")
        if base in current_holdings:
            continue  # 已持有
        if buy_history.get(s, 0) < REQUIRE_CONSISTENT_ROUNDS:
            print(f"{Fore.BLUE}🕒 跳过新币 {base}（未连续上榜）{Style.RESET_ALL}")
            continue

        price = client.get_symbol_price(s)
        if not price:
            continue
        allocation = (recommended_scores[s] / total_score) * usdt_balance
        qty = round((allocation * (1 - fee_rate)) / price, 4)
        if qty <= 0:
            continue

        print(f"{Fore.GREEN}💚 买入 {base}: 分配 {allocation:.2f} USDT, 数量 {qty}{Style.RESET_ALL}")
        if not simulate:
            client.place_order(s, "buy", size=str(qty))

        positions[base] = {
            "entry_price": round(price * (1 + fee_rate), 6),
            "timestamp": client.get_timestamp()
        }

    # 保存
    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)
    with open(BUY_HISTORY_FILE, "w") as f:
        json.dump(buy_history, f, indent=2)