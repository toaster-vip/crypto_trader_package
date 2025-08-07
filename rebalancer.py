import time
from decimal import Decimal, ROUND_DOWN
from config import CONFIG
from log_utils import log_info, log_trade_detail
from kucoin_api import to_symbol_pair

# 工具函数
def get_entry_price(pos):
    if isinstance(pos, dict):
        return Decimal(str(pos.get("entry_price", 0)))
    return Decimal("0")

def get_amount(pos):
    if isinstance(pos, dict):
        return Decimal(str(pos.get("amount", 0)))
    return Decimal("0")

TAKE_PROFIT = Decimal(str(CONFIG["TAKE_PROFIT"]))
STOP_LOSS = Decimal(str(CONFIG["STOP_LOSS"]))
TRAILING_STOP_PCT = Decimal(str(CONFIG["TRAILING_STOP_PCT"]))
MAX_POSITION_RATIO = Decimal(str(CONFIG["MAX_POSITION_RATIO"]))
MIN_BUY_AMOUNT = Decimal(str(CONFIG["MIN_BUY_AMOUNT"]))

# 推荐冷却期设置
COOLDOWN_ROUNDS = CONFIG.get("COOLDOWN_ROUNDS", 3)  # 冷却3轮（比如每4小时为1轮）

def rebalance_portfolio(
    top_symbols, balances, positions, place_order,
    price_map=None, dry_run=False, api=None,
    cooldown_pool=None, current_round=None, cooldown_rounds=COOLDOWN_ROUNDS
):
    """
    调仓逻辑（主流量化风格），集成冷却机制
    :param cooldown_pool: dict, 记录symbol -> 解禁轮次
    :param current_round: int, 当前轮次编号（主控建议每4小时一个轮次，可自定义）
    :param cooldown_rounds: int, 止盈/止损后冷却多少轮
    """
    if api is None:
        raise ValueError("必须传入唯一的 KuCoinClient api 实例！（主控请用 rebalance_portfolio(..., api=api)）")
    if cooldown_pool is None:  # 默认空dict
        cooldown_pool = {}
    if current_round is None:
        # 若未传，则以小时为单位（默认每4小时为一轮），建议主控传入
        current_round = int(time.time() // (3600 * 4))

    log_info(f"== 调仓轮 == Top池: {top_symbols}")
    usdt = Decimal(str(balances.get("USDT", 0)))
    cur_hold = {to_symbol_pair(k): v for k, v in positions.items() if get_amount(v) > 0}
    hold_syms = set(cur_hold.keys())
    top_syms_pair = [to_symbol_pair(s) for s in top_symbols]
    total_asset = usdt + sum(get_entry_price(pos) * get_amount(pos) for pos in cur_hold.values())
    per_pos = min(total_asset * MAX_POSITION_RATIO, usdt / max(1, len(top_syms_pair))) if top_syms_pair else Decimal("0")

    # ========== 1. 卖出所有应平仓币 ==========
    for symbol, pos in cur_hold.items():
        entry = get_entry_price(pos)
        amount = get_amount(pos)
        # 防御：行情API丢失、退市时跳过（不会崩溃）
        if price_map and symbol in price_map:
            cur_price_raw = price_map[symbol]
        else:
            cur_price_raw = api.get_symbol_price(symbol)
        if cur_price_raw is None:
            log_info(f"[跳过] {symbol} 无法获取当前价格，自动跳过卖出/持有决策！")
            continue
        cur_price = Decimal(str(cur_price_raw))
        pnl = (cur_price - entry) / (entry + Decimal('1e-8'))
        trade = {
            "type": "sell_candidate",
            "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": symbol,
            "amount": float(amount),
            "base_price": float(entry),
            "current_price": float(cur_price),
            "pnl_pct": float(pnl),
        }
        if symbol not in top_syms_pair and (pnl >= TAKE_PROFIT or pnl <= STOP_LOSS):
            trade["reason"] = "TP/SL"
            log_trade_detail(trade)
            if not dry_run:
                place_order('sell', symbol, float(amount))
                # 【卖出成功后，加入冷却池，当前轮+N轮】
                if cooldown_pool is not None and current_round is not None:
                    cooldown_pool[symbol] = current_round + cooldown_rounds
            log_info(f"[平仓] {symbol} 触发止盈止损，进入冷却{cooldown_rounds}轮")
        elif symbol not in top_syms_pair:
            log_info(f"[续持] {symbol} 非热点但未触发止盈止损，留仓")
        elif pnl >= TAKE_PROFIT:
            trade["reason"] = "TAKE_PROFIT"
            log_trade_detail(trade)
            if not dry_run:
                place_order('sell', symbol, float(amount))
                if cooldown_pool is not None and current_round is not None:
                    cooldown_pool[symbol] = current_round + cooldown_rounds
            log_info(f"[止盈] {symbol} 达到止盈，进入冷却{cooldown_rounds}轮")
        elif pnl <= STOP_LOSS:
            trade["reason"] = "STOP_LOSS"
            log_trade_detail(trade)
            if not dry_run:
                place_order('sell', symbol, float(amount))
                if cooldown_pool is not None and current_round is not None:
                    cooldown_pool[symbol] = current_round + cooldown_rounds
            log_info(f"[止损] {symbol} 触发止损，进入冷却{cooldown_rounds}轮")
        else:
            log_info(f"[持有] {symbol} 正常持有")

    # ========== 2. 卖出后刷新usdt余额 ==========
    if not dry_run:
        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))

    # ========== 3. 新热点买入 ==========
    for symbol in top_syms_pair:
        # 【买入前判断是否在冷却期】
        if cooldown_pool and cooldown_pool.get(symbol, 0) > current_round:
            log_info(f"[冷却中] {symbol} 在冷却期，跳过买入。")
            continue

        if symbol not in hold_syms and per_pos >= MIN_BUY_AMOUNT and usdt >= per_pos:
            # 步进修正
            limits = api.get_symbol_limits(symbol)
            funds_increment = Decimal(str(limits.get("minFunds", 0.01))) if limits else Decimal("0.01")
            rounded_amt = (per_pos // funds_increment) * funds_increment
            rounded_amt = rounded_amt.quantize(funds_increment, rounding=ROUND_DOWN)
            if rounded_amt < funds_increment:
                log_info(f"[跳过] {symbol} 可买金额不足步进要求（minFunds={funds_increment}），跳过！")
                continue
            log_info(f"[买入] {symbol} 买入金额: {rounded_amt:.8f}")
            if not dry_run:
                place_order('buy', symbol, float(rounded_amt))
            usdt -= rounded_amt
            if price_map and symbol in price_map:
                buy_price = float(price_map[symbol])
            else:
                buy_price_raw = api.get_symbol_price(symbol)
                if buy_price_raw is None:
                    log_info(f"[跳过] {symbol} 买入时无法获价，跳过！")
                    continue
                buy_price = float(buy_price_raw)
            log_trade_detail({
                "type": "buy",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": symbol,
                "amount": float(rounded_amt),
                "price": buy_price,
            })
    log_info("[调仓结束]")