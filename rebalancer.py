# rebalancer.py

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

    # 卖出非优先币种
    print("[DEBUG] 卖出非优先币种")
    for symbol in current_holdings:
        if symbol == "USDT":
            continue
        full = f"{symbol}-USDT"
        if full in recommended_symbols:
            rank = recommended_symbols.index(full) + 1
            if rank <= HOLD_THRESHOLD_RANK:
                continue
            score = recommended_scores.get(full, 0)
            min_required = max(recommended_scores.values()) * (1 - SCORE_DIFF_THRESHOLD)
            if score >= min_required:
                continue
        if not simulate:
            client.place_order(full, "sell", size=str(current_holdings[symbol]))
        positions.pop(symbol, None)

    # 获取交易账户余额
    trade_usdt = client.get_trade_account_balance("USDT")
    main_usdt = current_holdings.get("USDT", 0)
    available_usdt = trade_usdt
    print(f"{Fore.CYAN}💵 交易账户 USDT 余额: {trade_usdt:.4f}{Style.RESET_ALL}")

    if available_usdt <= 0 and main_usdt > 0:
        print(f"{Fore.YELLOW}⚠️ 尝试从主账户转入 {main_usdt} USDT{Style.RESET_ALL}")
        if not simulate:
            success = client.transfer_to_trade_account("USDT", amount=main_usdt)
            if success:
                time.sleep(2)
                trade_usdt = client.get_trade_account_balance("USDT")
                available_usdt = trade_usdt

    if available_usdt <= 0:
        print(f"{Fore.RED}❌ 无可用 USDT，跳过买入{Style.RESET_ALL}")
        return

    available_usdt *= (1 - reserve_ratio)

    # 买入历史
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
        allocation *= 0.998  # 保守减 0.2% 作为手续费缓冲

        symbol_limits = client.get_symbol_limits(s)
        if symbol_limits:
            min_funds = float(symbol_limits.get("minFunds", 0))
            min_size = float(symbol_limits.get("minSize", 0))
            max_size = float(symbol_limits.get("maxSize", 1e10))
            step_size = float(symbol_limits.get("stepSize", 0.000001))
        else:
            min_funds = 0
            min_size = 0
            max_size = 1e10
            step_size = 0.000001

        if allocation < min_funds:
            print(f"{Fore.YELLOW}⚠️ 分配金额 {allocation:.2f} 小于最小下单金额 {min_funds}，跳过 {base}{Style.RESET_ALL}")
            continue

        raw_qty = allocation / price
        qty = float((Decimal(str(raw_qty)).quantize(Decimal(str(step_size)), rounding=ROUND_DOWN)))

        if qty < min_size or qty > max_size:
            print(f"{Fore.YELLOW}⚠️ 数量 {qty} 不满足限制 [{min_size} ~ {max_size}]，跳过 {base}{Style.RESET_ALL}")
            continue

        print(f"{Fore.LIGHTGREEN_EX}📈 买入 {base}: 分配={allocation:.2f} USDT（市价单）{Style.RESET_ALL}")
        if not simulate:
            resp = client.place_order(s, "buy", size=allocation)  # ✅ 市价买入，传 USDT
            if not resp:
                print(f"{Fore.RED}[ERROR] 下单失败，跳过 {base}{Style.RESET_ALL}")
                continue

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