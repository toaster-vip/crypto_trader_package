# rebalancer.py
import time
import json
import os
from decimal import Decimal, ROUND_DOWN
from config import CONFIG
from log_utils import log_info, log_trade_detail
from kucoin_api import to_symbol_pair

ENTRY_PRICE_FILE = "/home/linuxuser/crypto_trader_package/entry_price_state.json"
COOLDOWN_FILE = "/home/linuxuser/crypto_trader_package/cooldown_pool.json"

def load_entry_price_state():
    if os.path.exists(ENTRY_PRICE_FILE):
        with open(ENTRY_PRICE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_entry_price_state(state):
    with open(ENTRY_PRICE_FILE, "w") as f:
        json.dump(state, f)

def load_cooldown_pool():
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cooldown_pool(pool):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(pool, f)

def calc_weighted_avg_entry_price(api, symbol, amount_min=1e-6):
    fills = api.get_fills(symbol, side="buy", limit=100)
    total_amt = 0.0
    total_cost = 0.0
    for f in fills:
        try:
            sz = float(f.get("size", 0))
            px = float(f.get("price", 0))
            if sz > amount_min and px > 0:
                total_amt += sz
                total_cost += sz * px
        except Exception:
            continue
    if total_amt > 0:
        return Decimal(str(total_cost / total_amt))
    return Decimal("0")

def get_dynamic_entry_price(symbol, pos, entry_price_state, api=None):
    sym = to_symbol_pair(symbol)
    entry_price = entry_price_state.get(sym)
    if entry_price is not None and float(entry_price) > 0:
        return Decimal(str(entry_price))
    pos_entry = pos.get("entry_price", 0)
    if float(pos_entry) > 0:
        return Decimal(str(pos_entry))
    if api is not None:
        weighted = calc_weighted_avg_entry_price(api, sym)
        if weighted > 0:
            log_info(f"[entry_price] {sym} 回填加权均价: {weighted}")
            return weighted
    return Decimal("0")

TAKE_PROFIT = Decimal(str(CONFIG["TAKE_PROFIT"]))
STOP_LOSS = Decimal(str(CONFIG["STOP_LOSS"]))
TRAILING_STOP_PCT = Decimal(str(CONFIG["TRAILING_STOP_PCT"]))
MAX_POSITION_RATIO = Decimal(str(CONFIG["MAX_POSITION_RATIO"]))
MIN_BUY_AMOUNT = Decimal(str(CONFIG["MIN_BUY_AMOUNT"]))
COOLDOWN_ROUNDS = CONFIG.get("COOLDOWN_ROUNDS", 3)

def get_amount(pos):
    if isinstance(pos, dict):
        return Decimal(str(pos.get("amount", 0)))
    return Decimal("0")

def pretty_positions(positions):
    return {k: float(get_amount(v)) for k, v in positions.items()}

def pretty_prices(prices, syms=None):
    if not syms:
        return prices
    return {k: float(prices.get(k, 0)) for k in syms}

def print_snapshot(api, tag="", extra_syms=None):
    """按 LOG_DETAIL 控噪"""
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    if CONFIG.get("LOG_DETAIL", True):
        all_prices = api.get_all_prices() or {}
        syms = list(positions.keys())
        if extra_syms:
            syms = list(set(syms + list(extra_syms)))
        price_map = pretty_prices(all_prices, syms)
        log_info(f"\n====== {tag}账户快照 ======")
        log_info(f"[账户余额] USDT={balances.get('USDT',0)}, 详情: {balances}")
        log_info(f"[持有币]   {pretty_positions(positions)}")
        log_info(f"[币价]     {price_map}")
        log_info("====== End 快照 ======\n")
    else:
        log_info(f"[快照:{tag}] USDT={balances.get('USDT',0)} 持仓数={len(positions)}")

def print_cooldown_pool(cooldown_pool, current_round):
    if not CONFIG.get("LOG_DETAIL", True):
        active = sum(1 for r in cooldown_pool.values() if r > current_round)
        log_info(f"[冷却池] 活跃={active}")
        return
    log_info(f"[冷却名单]（当前轮:{current_round}）:")
    has_active = False
    for sym, round_num in cooldown_pool.items():
        remain = round_num - current_round
        if remain > 0:
            has_active = True
            log_info(f"   {sym}: 剩余{remain}轮")
    if not has_active:
        log_info(f"   当前无冷却币。")

def rebalance_portfolio(
    top_symbols, balances, positions, place_order,
    price_map=None, dry_run=False, api=None,
    cooldown_pool=None, current_round=None, cooldown_rounds=COOLDOWN_ROUNDS
):
    if api is None:
        raise ValueError("必须传入唯一的 KuCoinClient api 实例！（主控请用 rebalance_portfolio(..., api=api)）")
    if cooldown_pool is None:
        cooldown_pool = load_cooldown_pool()
    if current_round is None:
        current_round = int(time.time() // (3600 * 4))
    entry_price_state = load_entry_price_state()

    top_syms_pair = [to_symbol_pair(s) for s in (top_symbols or [])]

    # 1. 买前快照
    print_snapshot(api, tag="买入/卖出前", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    # 实时获取最新资金/持仓/币价
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices() or {}

    usdt = Decimal(str(balances.get("USDT", 0)))
    cur_hold = {to_symbol_pair(k): v for k, v in positions.items() if get_amount(v) > 0}

    # 用 entry_price_state/weighted 填充估值；失败则估值为0（但不强平）
    total_asset = usdt + sum(
        get_dynamic_entry_price(k, v, entry_price_state, api=api) * get_amount(v)
        for k, v in cur_hold.items()
    )
    # 计算位置上限（买入阶段使用）
    _ = min(total_asset * MAX_POSITION_RATIO, usdt / max(1, len(top_syms_pair))) if top_syms_pair else Decimal("0")

    # ========== 1) 先处理 卖出/止盈/止损 ==========
    sold_count = 0
    for symbol, pos in cur_hold.items():
        sym = to_symbol_pair(symbol)
        amount = get_amount(pos)

        entry = get_dynamic_entry_price(sym, pos, entry_price_state, api=api)
        cur_price_raw = all_prices.get(sym, None) or api.get_symbol_price(sym)
        if cur_price_raw is None:
            log_info(f"[跳过] {sym} 无法获取当前价格，跳过卖出/持有决策。")
            continue
        cur_price = Decimal(str(cur_price_raw))

        if entry <= 0:
            # 不强平；仅提示
            log_info(f"[警告] {sym} 缺少有效买入价（entry<=0），已跳过卖出/止损/止盈决策。")
            continue

        pnl = (cur_price - entry) / (entry + Decimal('1e-8'))

        # 止损
        if pnl <= STOP_LOSS:
            trade = {
                "type": "sell_candidate",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": sym,
                "amount": float(amount),
                "base_price": float(entry),
                "current_price": float(cur_price),
                "pnl_pct": float(pnl),
                "reason": "STOP_LOSS"
            }
            log_trade_detail(trade)
            if not dry_run:
                place_order('sell', sym, float(amount))
                cooldown_pool[sym] = current_round + cooldown_rounds
                entry_price_state.pop(sym, None)
            log_info(f"[止损] {sym} 触发止损并冷却{cooldown_rounds}轮 | 买入价={entry} | 当前价={cur_price} | 盈亏={pnl:.4%}")
            sold_count += 1
            continue

        # 动态止盈（热点内才上移）
        if sym in top_syms_pair and pnl >= TAKE_PROFIT:
            entry_price_state[sym] = float(cur_price)
            log_info(f"[动态止盈] {sym} 达止盈线且仍在TopN，上移entry至 {cur_price} | 原entry: {entry} | 盈亏={pnl:.4%}")
            continue

        # 续持
        if CONFIG.get("LOG_DETAIL", True):
            log_info(f"[持有] {sym} | entry={entry} | cur={cur_price} | pnl={pnl:.4%}")

    # 2) 卖出后快照
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices() or {}
    print_snapshot(api, tag="卖出后", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    # 3) 新热点买入
    buy_count = 0
    # 提前获取一次余额，避免循环重复请求
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    usdt = Decimal(str(balances.get("USDT", 0)))
    # 提前获取一次 limits 兜底值
    minfunds_fallback = Decimal(str(MIN_BUY_AMOUNT))

    # 计算分配
    top_count = max(1, len(top_syms_pair)) if top_syms_pair else 0
    per_pos_usdt = min(usdt * MAX_POSITION_RATIO, usdt / top_count) if top_count else Decimal("0")

    for symbol in top_syms_pair:
        sym = to_symbol_pair(symbol)

        # 冷却池过滤
        cooldown = cooldown_pool.get(sym, 0)
        if cooldown > current_round:
            if CONFIG.get("LOG_DETAIL", True):
                log_info(f"[冷却中] {sym} 剩余{cooldown-current_round}轮，跳过。")
            continue

        # 已持有跳过
        positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
        hold_syms = set(to_symbol_pair(k) for k in positions.keys() if get_amount(positions[k]) > 0)
        if sym in hold_syms:
            continue

        # 步进限制
        limits = api.get_symbol_limits(sym) or {}
        funds_increment = Decimal(str(limits.get("minFunds", minfunds_fallback)))

        # 四舍五入到交易所步进
        rounded_amt = (Decimal(per_pos_usdt) // funds_increment) * funds_increment
        rounded_amt = rounded_amt.quantize(funds_increment, rounding=ROUND_DOWN)

        # 余额再确认
        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))
        if usdt < funds_increment or rounded_amt < funds_increment:
            if CONFIG.get("LOG_DETAIL", True):
                log_info(f"[跳过] {sym} 可买金额{rounded_amt} 或余额{usdt} 不足 minFunds={funds_increment}。")
            continue

        log_info(f"[买入] {sym} 金额: {rounded_amt:.8f}")
        if not dry_run:
            orderid = place_order('buy', sym, float(rounded_amt))
            entry_price = api.get_symbol_price(sym)
            if entry_price is not None:
                entry_price_state[sym] = float(entry_price)
            log_trade_detail({
                "type": "buy",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": sym,
                "amount": float(rounded_amt),
                "price": float(entry_price) if entry_price is not None else "NA",
                "orderid": orderid,
            })
        buy_count += 1
        # 更新余额，避免超配
        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))
        remaining_slots = max(1, (top_count - buy_count)) if top_count else 1
        per_pos_usdt = min(usdt * MAX_POSITION_RATIO, usdt / remaining_slots)

    # 4) 买后快照
    print_snapshot(api, tag="买入后", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    # 5) 落盘
    save_entry_price_state(entry_price_state)
    save_cooldown_pool(cooldown_pool)

    log_info("[调仓结束]")
    if sold_count == 0:
        log_info("本轮未发生卖出。")
    if buy_count == 0 and top_syms_pair:
        log_info("本轮未发生买入（可能因冷却/余额/步进限制）。")