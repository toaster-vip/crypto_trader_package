# rebalancer.py

import os
import json
import time
from config import CONFIG
from colorama import Fore, Style

BUY_HISTORY_FILE = os.path.join(CONFIG["LOG_DIR"], "buy_history.json")
REBALANCE_CFG = CONFIG["REBALANCE"]
HOLD_THRESHOLD_RANK = REBALANCE_CFG["HOLD_THRESHOLD_RANK"]
SCORE_DIFF_THRESHOLD = REBALANCE_CFG["SCORE_DIFF_THRESHOLD"]
REQUIRE_CONSISTENT_ROUNDS = REBALANCE_CFG["REQUIRE_CONSISTENT_ROUNDS"]

def rebalance_portfolio(client, current_holdings, recommended_tuples, positions_file):
    print(f"[DEBUG] 🔄 开始执行 rebalance_portfolio()")
    simulate = CONFIG["SIMULATE"]
    fee_rate = 0.001
    take_profit = CONFIG["TRADE"]["TAKE_PROFIT"]
    stop_loss = CONFIG["TRADE"]["STOP_LOSS"]
    reserve_ratio = CONFIG["RESERVE_RATIO"]

    recommended_symbols = [s for s, _ in recommended_tuples]
    recommended_scores = {s: sc for s, sc in recommended_tuples}
    top_symbols = [s for s, _ in recommended_tuples[:3]]

    # 加载历史持仓
    print("[DEBUG] 读取历史持仓记录")
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            positions = json.load(f)
    else:
        positions = {}

    # 止盈止损逻辑
    for symbol, info in positions.copy().items():
        if symbol not in current_holdings:
            continue
        full_symbol = f"{symbol}-USDT"
        qty = float(current_holdings[symbol])
        current_price = client.get_symbol_price(full_symbol)
        entry_price = info["entry_price"]
        if not current_price:
            print(f"[DEBUG] 无法获取价格 {full_symbol}")
            continue
        pnl = (current_price - entry_price) / entry_price
        print(f"[DEBUG] 检查 {symbol} PnL: {pnl:.2%}")
        if pnl >= take_profit:
            print(f"{Fore.MAGENTA}🎯 止盈卖出 {symbol} 盈利 {pnl:.2%}{Style.RESET_ALL}")
        elif pnl <= stop_loss:
            print(f"{Fore.RED}🛑 止损卖出 {symbol} 亏损 {pnl:.2%}{Style.RESET_ALL}")
        else:
            continue
        if not simulate:
            client.place_order(full_symbol, "sell", size=str(qty))
        positions.pop(symbol, None)

    # 输出当前持仓与推荐币种对比
    print(f"{Fore.MAGENTA}[DEBUG] 当前持仓评分参考：{Style.RESET_ALL}")
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        score = recommended_scores.get(full, "N/A")
        print(f"{Fore.MAGENTA}- {full}: 评分 = {score}{Style.RESET_ALL}")

    # 卖出非优先币种
    print("[DEBUG] 卖出非优先币种")
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        if full in recommended_symbols:
            rank = recommended_symbols.index(full) + 1
            if rank <= HOLD_THRESHOLD_RANK:
                print(f"{Fore.LIGHTBLACK_EX}🔒 保留 {symbol}，在 Top{HOLD_THRESHOLD_RANK}{Style.RESET_ALL}")
                continue
            score = recommended_scores.get(full, 0)
            min_required = max(recommended_scores.values()) * (1 - SCORE_DIFF_THRESHOLD)
            if score >= min_required:
                print(f"{Fore.LIGHTBLACK_EX}🔒 保留 {symbol}，评分差异不足{SCORE_DIFF_THRESHOLD*100:.1f}%{Style.RESET_ALL}")
                continue
        print(f"{Fore.LIGHTBLACK_EX}🧹 卖出非优先币种 {symbol}{Style.RESET_ALL}")
        if not simulate:
            client.place_order(full, "sell", size=str(current_holdings[symbol]))
        positions.pop(symbol, None)

    # 获取交易账户余额
    trade_usdt = client.get_trade_account_balance("USDT")
    main_usdt = current_holdings.get("USDT", 0)
    available_usdt = trade_usdt
    print(f"{Fore.CYAN}💵 交易账户 USDT 余额: {trade_usdt:.4f}{Style.RESET_ALL}")

    if available_usdt <= 0:
        if main_usdt > 0:
            print(f"{Fore.YELLOW}⚠️ 交易账户余额不足，尝试从主账户转入 {main_usdt} USDT{Style.RESET_ALL}")
            if not simulate:
                success = client.transfer_to_trade_account("USDT", amount=main_usdt)
                if success:
                    time.sleep(2)
                    trade_usdt = client.get_trade_account_balance("USDT")
                    available_usdt = trade_usdt
                    print(f"{Fore.CYAN}🔄 转账后交易账户 USDT 余额: {available_usdt:.4f}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}❌ USDT 主/交易账户余额均为 0，跳过买入{Style.RESET_ALL}")
            with open(positions_file, "w") as f:
                json.dump(positions, f, indent=2)
            return

    available_usdt *= (1 - reserve_ratio)

    # 加载买入历史
    if os.path.exists(BUY_HISTORY_FILE):
        with open(BUY_HISTORY_FILE, "r") as f:
            buy_history = json.load(f)
    else:
        buy_history = {}

    for s, _ in recommended_tuples:
        buy_history[s] = buy_history.get(s, 0) + 1
    for s in list(buy_history):
        if s not in recommended_scores:
            buy_history[s] = 0

    # 动态买入逻辑
    total_score = sum([recommended_scores[s] for s in top_symbols])
    for s in top_symbols:
        base = s.replace("-USDT", "")
        score = recommended_scores[s]
        if base in current_holdings:
            continue
        if buy_history.get(s, 0) < REQUIRE_CONSISTENT_ROUNDS:
            continue
        price = client.get_symbol_price(s)
        if not price:
            continue
        allocation = (score / total_score) * available_usdt
        qty = round((allocation * (1 - fee_rate)) / price, 4)
        if qty <= 0:
            continue
        print(f"{Fore.LIGHTGREEN_EX}📈 买入 {base}: 分配={allocation:.2f}, 数量={qty}{Style.RESET_ALL}")
        if not simulate:
            client.place_order(s, "buy", size=str(qty))
        positions[base] = {
            "entry_price": round(price * (1 + fee_rate), 6),
            "timestamp": client.get_timestamp()
        }

    # 保存记录
    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)
    with open(BUY_HISTORY_FILE, "w") as f:
        json.dump(buy_history, f, indent=2)
    print(f"[DEBUG] ✅ rebalance_portfolio() 执行完毕")