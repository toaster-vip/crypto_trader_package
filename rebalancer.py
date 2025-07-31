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

    print(f"[DEBUG] ✅ rebalance_portfolio() 执行完毕")
    # 加载历史持仓
    print("[DEBUG] 读取历史持仓记录")
    if os.path.exists(positions_file):
        with open(positions_file, "r") as f:
            positions = json.load(f)
    else:
        positions = {}

    # 止盈/止损逻辑
    print("[DEBUG] 执行止盈/止损逻辑")
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

    # 输出当前持仓和推荐对比
    print(f"{Fore.MAGENTA}[DEBUG] 当前真实持仓币种评分对照：{Style.RESET_ALL}")
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        score = recommended_scores.get(full, "N/A")
        print(f"{Fore.MAGENTA}- {full}: 评分 = {score}{Style.RESET_ALL}")

    # 卖出非优先币种
    print("[DEBUG] 卖出非优先币种逻辑执行中")
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        if full in recommended_symbols:
            rank = recommended_symbols.index(full) + 1
            if rank <= HOLD_THRESHOLD_RANK:
                print(f"{Fore.LIGHTBLACK_EX}🔒 保留当前币种 {symbol}，因仍在Top{HOLD_THRESHOLD_RANK}{Style.RESET_ALL}")
                continue
            current_score = recommended_scores.get(full, 0)
            min_required = max(recommended_scores.values()) * (1 - SCORE_DIFF_THRESHOLD)
            if current_score >= min_required:
                print(f"{Fore.LIGHTBLACK_EX}🔒 保留当前币种 {symbol}，分数相差不大（{current_score:.4f} vs {min_required:.4f}）{Style.RESET_ALL}")
                continue
        print(f"[DEBUG] 准备卖出非推荐币 {symbol}")
        if symbol in positions:
            print(f"{Fore.LIGHTBLACK_EX}🧹 卖出非优先币种 {symbol}{Style.RESET_ALL}")
            if not simulate:
                client.place_order(full, "sell", size=str(current_holdings[symbol]))
            positions.pop(symbol, None)

    # 检查 USDT 可用余额
    total_usdt = current_holdings.get("USDT", 0)
    usdt_balance = total_usdt * (1 - reserve_ratio)
    print(f"{Fore.CYAN}💵 当前 USDT 总余额: {total_usdt:.4f}, 可用: {usdt_balance:.4f}（保留 {reserve_ratio*100:.1f}%）{Style.RESET_ALL}")

    if usdt_balance <= 0:
        print(f"{Fore.YELLOW}⚠️ 可用 USDT 不足，尝试从 Auto Earn 自动赎回...{Style.RESET_ALL}")
        """
        if not simulate:
            redeemed = client.redeem_autoearn("USDT", amount=None)
            if redeemed:
                print(f"{Fore.GREEN}✅ 成功赎回理财资产 USDT{Style.RESET_ALL}")
                time.sleep(3)
                current_holdings = client.get_account_holdings()
                total_usdt = current_holdings.get("USDT", 0)
                usdt_balance = total_usdt * (1 - reserve_ratio)
                print(f"{Fore.CYAN}💵 赎回后 USDT 总余额: {total_usdt:.4f}, 可用: {usdt_balance:.4f}{Style.RESET_ALL}")
            else:
                print(f"{Fore.RED}❌ Auto Earn 赎回失败，跳过本轮买入{Style.RESET_ALL}")
                with open(positions_file, "w") as f:
                    json.dump(positions, f, indent=2)
                return
        """

    # 加载买入历史
    print("[DEBUG] 加载买入历史 buy_history.json")
    if os.path.exists(BUY_HISTORY_FILE):
        with open(BUY_HISTORY_FILE, "r") as f:
            buy_history = json.load(f)
    else:
        buy_history = {}

    for s, _ in recommended_tuples:
        buy_history[s] = buy_history.get(s, 0) + 1
    for s in list(buy_history):
        if s not in recommended_symbols:
            buy_history[s] = 0

    # 动态买入逻辑
    print("[DEBUG] 执行动态买入逻辑")
    total_score = sum([recommended_scores[s] for s in top_symbols])
    print(f"{Fore.CYAN}📊 Top评分币种总分: {total_score:.4f}{Style.RESET_ALL}")
    for s in top_symbols:
        base = s.replace("-USDT", "")
        score = recommended_scores[s]
        print(f"[DEBUG] 处理 {s}: 当前评分 {score}")
        if base in current_holdings:
            print(f"{Fore.YELLOW}⏸️ 跳过已有持仓 {base}{Style.RESET_ALL}")
            continue
        if buy_history.get(s, 0) < REQUIRE_CONSISTENT_ROUNDS:
            print(f"{Fore.BLUE}🕒 跳过新币 {base}（未连续上榜）{Style.RESET_ALL}")
            continue

        price = client.get_symbol_price(s)
        if not price:
            print(f"{Fore.RED}⚠️ 获取币价失败 {s}{Style.RESET_ALL}")
            continue
        allocation = (score / total_score) * usdt_balance
        qty = round((allocation * (1 - fee_rate)) / price, 4)

        print(f"{Fore.LIGHTGREEN_EX}📈 {base}: 评分={score:.4f}, 分配={allocation:.2f}USDT, 币价={price:.4f}, 下单量={qty}{Style.RESET_ALL}")

        if qty <= 0:
            print(f"{Fore.LIGHTBLACK_EX}⚠️ 数量为0，跳过买入 {base}{Style.RESET_ALL}")
            continue

        if not simulate:
            print(f"[DEBUG] 执行买入 {s} 数量 {qty}")
            client.place_order(s, "buy", size=str(qty))

        positions[base] = {
            "entry_price": round(price * (1 + fee_rate), 6),
            "timestamp": client.get_timestamp()
        }

    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)
    with open(BUY_HISTORY_FILE, "w") as f:
        json.dump(buy_history, f, indent=2)

    print(f"[DEBUG] ✅ rebalance_portfolio() 执行完毕")