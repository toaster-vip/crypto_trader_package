import os
import json
import time
from config import CONFIG
from colorama import Fore, Style
from decimal import Decimal, ROUND_DOWN

BUY_HISTORY_FILE = os.path.join(CONFIG["LOG_DIR"], "buy_history.json")
REBALANCE_CFG = CONFIG["REBALANCE"]
HOLD_THRESHOLD_RANK = REBALANCE_CFG["HOLD_THRESHOLD_RANK"]
SCORE_DIFF_THRESHOLD = REBALANCE_CFG["SCORE_DIFF_THRESHOLD"]
REQUIRE_CONSISTENT_ROUNDS = REBALANCE_CFG["REQUIRE_CONSISTENT_ROUNDS"]
MAX_ALLOCATION_RATIO = 0.2
MIN_VOLUME_24H = 50000
MIN_PRICE = 0.005
RESERVE_RATIO = CONFIG["RESERVE_RATIO"]
FEE_RATE = 0.001
TAKE_PROFIT = CONFIG["TRADE"]["TAKE_PROFIT"]
STOP_LOSS = CONFIG["TRADE"]["STOP_LOSS"]

def rebalance_portfolio(client, current_holdings, recommended_tuples, positions_file):
    print(f"[DEBUG] 🔄 rebalance_portfolio() 开始")
    simulate = CONFIG["SIMULATE"]
    recommended_symbols = [s for s, _ in recommended_tuples]
    recommended_scores = {s: sc for s, sc in recommended_tuples}
    top_symbols = [s for s, _ in recommended_tuples[:5]]

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
        price = client.get_symbol_price(full_symbol)
        if not price:
            continue
        entry = info["entry_price"]
        pnl = (price - entry) / entry
        if pnl >= TAKE_PROFIT:
            print(f"{Fore.MAGENTA}🎯 止盈卖出 {symbol} 盈利 {pnl:.2%}{Style.RESET_ALL}")
        elif pnl <= STOP_LOSS:
            print(f"{Fore.RED}🛑 止损卖出 {symbol} 亏损 {pnl:.2%}{Style.RESET_ALL}")
        else:
            continue
        if not simulate:
            client.place_order(full_symbol, "sell", size=str(qty))
        positions.pop(symbol, None)

    # 卖出非优先币
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        if full in recommended_symbols:
            rank = recommended_symbols.index(full)
            if rank < HOLD_THRESHOLD_RANK:
                continue
            score = recommended_scores.get(full, 0)
            if score >= max(recommended_scores.values()) * (1 - SCORE_DIFF_THRESHOLD):
                continue
        print(f"{Fore.LIGHTBLACK_EX}🧹 卖出非优先币种 {symbol}{Style.RESET_ALL}")
        if not simulate:
            client.place_order(full, "sell", size=str(current_holdings[symbol]))
        positions.pop(symbol, None)

    # 获取余额
    trade_usdt = client.get_trade_account_balance("USDT")
    main_usdt = current_holdings.get("USDT", 0)
    usdt = trade_usdt
    if usdt <= 0 and main_usdt > 0:
        if not simulate:
            client.transfer_to_trade_account("USDT", main_usdt)
            time.sleep(2)
        usdt = client.get_trade_account_balance("USDT")
    if usdt <= 0:
        print(f"{Fore.RED}❌ 无可用 USDT，跳过买入{Style.RESET_ALL}")
        return

    usdt *= (1 - RESERVE_RATIO)
    max_allocation = usdt * MAX_ALLOCATION_RATIO

    # 加载历史推荐
    if os.path.exists(BUY_HISTORY_FILE):
        with open(BUY_HISTORY_FILE, "r") as f:
            history = json.load(f)
    else:
        history = {}
    for s, _ in recommended_tuples:
        history[s] = history.get(s, 0) + 1

    # 归一化+衰减打分
    scores = [recommended_scores[s] for s in top_symbols]
    total_score = sum(scores)
    if total_score == 0:
        print("[WARN] 总评分为0，跳过买入")
        return

    for s in top_symbols:
        base = s.replace("-USDT", "")
        if base in current_holdings:
            continue
        if history.get(s, 0) < REQUIRE_CONSISTENT_ROUNDS:
            continue
        mdata = client.get_market_data(s)
        price = mdata.get("price")
        vol = mdata.get("vol", 0)
        if not price or price < MIN_PRICE or vol < MIN_VOLUME_24H:
            print(f"{Fore.YELLOW}⚠️ {s} 价格/成交量不合规，跳过{Style.RESET_ALL}")
            continue

        score = recommended_scores[s]
        weight = score / total_score
        weight *= (0.8 ** top_symbols.index(s))  # 衰减

        allocation = usdt * weight
        if allocation > max_allocation:
            allocation = max_allocation

        limits = client.get_symbol_limits(s)
        min_funds = limits.get("minFunds", 0)
        step = limits.get("stepSize", 0.000001)

        if allocation < min_funds:
            print(f"{Fore.YELLOW}⚠️ {s} 分配 {allocation:.2f} 小于最小下单额 {min_funds}{Style.RESET_ALL}")
            continue

        allocation = float(Decimal(str(allocation)).quantize(Decimal("0.01"), rounding=ROUND_DOWN))

        print(f"{Fore.GREEN}📈 买入 {base}: 分配={allocation:.2f} USDT（市价单）{Style.RESET_ALL}")
        if not simulate:
            resp = client.place_order(s, "buy", size=str(allocation))
            if not resp:
                print(f"{Fore.RED}[ERROR] 下单失败，跳过 {base}{Style.RESET_ALL}")
                continue
        positions[base] = {
            "entry_price": round(price * (1 + FEE_RATE), 6),
            "timestamp": client.get_timestamp()
        }

    with open(positions_file, "w") as f:
        json.dump(positions, f, indent=2)
    with open(BUY_HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    print(f"[DEBUG] ✅ rebalance_portfolio() 执行完毕")