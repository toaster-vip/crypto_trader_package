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
    total_amt = 0
    total_cost = 0
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
            log_info(f"[entry_price] {sym} 本地/持仓为0，已自动回填加权均价: {weighted}")
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
    """格式化输出持仓dict"""
    return {k: float(get_amount(v)) for k, v in positions.items()}

def pretty_prices(prices, syms=None):
    """格式化输出币价"""
    if not syms:
        return prices
    return {k: float(prices.get(k, 0)) for k in syms}

def print_snapshot(api, tag="", extra_syms=None):
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices()
    syms = list(positions.keys())
    if extra_syms:
        syms = list(set(syms + list(extra_syms)))
    price_map = pretty_prices(all_prices, syms)
    log_info(f"\n====== {tag}账户快照 ======")
    log_info(f"[账户余额] USDT={balances.get('USDT',0)}, 详情: {balances}")
    log_info(f"[持有币]   {pretty_positions(positions)}")
    log_info(f"[币价]     {price_map}")
    log_info("====== End 快照 ======\n")

def print_cooldown_pool(cooldown_pool, current_round):
    log_info(f"[冷却名单]（当前轮:{current_round}）:")
    for sym, round_num in cooldown_pool.items():
        remain = round_num - current_round
        if remain > 0:
            log_info(f"   {sym}: 剩余{remain}轮")
    if not any(round_num > current_round for round_num in cooldown_pool.values()):
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

    top_syms_pair = [to_symbol_pair(s) for s in top_symbols]

    # 1. 买前快照
    print_snapshot(api, tag="买入/卖出前", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    # 实时获取最新资金/持仓/币价
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices()

    usdt = Decimal(str(balances.get("USDT", 0)))
    cur_hold = {to_symbol_pair(k): v for k, v in positions.items() if get_amount(v) > 0}
    hold_syms = set(cur_hold.keys())

    total_asset = usdt + sum(
        get_dynamic_entry_price(k, v, entry_price_state, api=api) * get_amount(v) for k, v in cur_hold.items()
    )
    per_pos = min(total_asset * MAX_POSITION_RATIO, usdt / max(1, len(top_syms_pair))) if top_syms_pair else Decimal("0")

    # ========== 1. 卖出/动态止盈 ==========
    sold_count = 0
    for symbol, pos in cur_hold.items():
        sym = to_symbol_pair(symbol)
        amount = get_amount(pos)
        entry = get_dynamic_entry_price(sym, pos, entry_price_state, api=api)
        # 取最新价
        cur_price_raw = all_prices.get(sym, None) or api.get_symbol_price(sym)
        if cur_price_raw is None:
            log_info(f"[跳过] {sym} 无法获取当前价格，自动跳过卖出/持有决策！")
            continue
        cur_price = Decimal(str(cur_price_raw))
        pnl = (cur_price - entry) / (entry + Decimal('1e-8')) if entry > 0 else Decimal("0")

        # 临时强平逻辑
        if entry <= 0:
            log_info(f"[临时修正] {sym} 由于买入价为0，直接强平卖出！")
            if not dry_run:
                place_order('sell', sym, float(amount))
                if cooldown_pool is not None:
                    cooldown_pool[sym] = current_round + cooldown_rounds
                if sym in entry_price_state:
                    entry_price_state.pop(sym)
            sold_count += 1
            continue

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
                if cooldown_pool is not None:
                    cooldown_pool[sym] = current_round + cooldown_rounds
                if sym in entry_price_state:
                    entry_price_state.pop(sym)
            log_info(
                f"[止损] {sym} 触发止损，卖出并冷却{cooldown_rounds}轮 | 买入价={entry} | 当前价={cur_price} | 盈亏={pnl:.4%}"
            )
            sold_count += 1
            continue

        # 动态止盈
        if sym in top_syms_pair and pnl >= TAKE_PROFIT:
            entry_price_state[sym] = float(cur_price)
            log_info(
                f"[动态止盈] {sym} 达到止盈线且仍为TopN，动态上移entry price: {cur_price} | 原entry: {entry} | 当前价={cur_price} | 盈亏={pnl:.4%}"
            )
            continue

        # 普通续持
        if sym not in top_syms_pair:
            log_info(
                f"[续持] {sym} 非热点但未触发止盈止损，留仓 | 买入价={entry} | 当前价={cur_price} | 盈亏={pnl:.4%} | 止损线={STOP_LOSS:.2%} | 止盈线={TAKE_PROFIT:.2%}"
            )
        else:
            log_info(
                f"[持有] {sym} 正常持有 | 买入价={entry} | 当前价={cur_price} | 盈亏={pnl:.4%} | 止损线={STOP_LOSS:.2%} | 止盈线={TAKE_PROFIT:.2%}"
            )

    # ========== 2. 卖出后快照 ==========
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices()
    print_snapshot(api, tag="卖出后", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    # ========== 3. 新热点买入 ==========
    buy_count = 0
    for symbol in top_syms_pair:
        sym = to_symbol_pair(symbol)
        # 冷却池过滤
        cooldown = cooldown_pool.get(sym, 0)
        if cooldown > current_round:
            log_info(f"[冷却中] {sym} 在冷却期（剩余{cooldown-current_round}轮），跳过买入。")
            continue

        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))
        positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
        hold_syms = set(to_symbol_pair(k) for k in positions.keys() if get_amount(positions[k]) > 0)
        if sym in hold_syms:
            log_info(f"[跳过] {sym} 已持有，跳过买入。")
            continue
        # 实时再拉全市场价
        all_prices = api.get_all_prices()
        limits = api.get_symbol_limits(sym)
        funds_increment = Decimal(str(limits.get("minFunds", 0.01))) if limits else Decimal("0.01")
        per_pos = min(
            usdt * MAX_POSITION_RATIO,
            usdt / max(1, len(top_syms_pair))
        )
        rounded_amt = (Decimal(per_pos) // funds_increment) * funds_increment
        rounded_amt = rounded_amt.quantize(funds_increment, rounding=ROUND_DOWN)
        if rounded_amt < funds_increment:
            log_info(
                f"[跳过] {sym} 可买金额 {rounded_amt} 不足步进要求（minFunds={funds_increment}），跳过！"
                f" 资金: USDT={usdt}, MAX_POSITION_RATIO={MAX_POSITION_RATIO}, topN={len(top_syms_pair)}"
            )
            continue
        if usdt < funds_increment:
            log_info(f"[跳过] {sym} 可用资金 {usdt} 不足minFunds={funds_increment}，无法买入。")
            continue
        log_info(f"[买入] {sym} 买入金额: {rounded_amt:.8f}")
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
        # 买后立即更新usdt余额，保证资金分配不超额
        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))

    # ========== 4. 买后快照 ==========
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices()
    print_snapshot(api, tag="买入后", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    # ========== 5. 记录结果 ==========
    save_entry_price_state(entry_price_state)
    save_cooldown_pool(cooldown_pool)

    log_info("[调仓结束]")
    if sold_count == 0:
        log_info("本轮未发生任何卖出，原因：当前无需要卖出的币或所有持有币均未触发卖出条件。")
    if buy_count == 0:
        # 输出买入失败原因
        log_info("本轮未发生任何买入，原因如下：")
        for symbol in top_syms_pair:
            sym = to_symbol_pair(symbol)
            cooldown = cooldown_pool.get(sym, 0)
            if cooldown > current_round:
                log_info(f"  - {sym} 在冷却期（剩余{cooldown-current_round}轮）")
            else:
                balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
                usdt = Decimal(str(balances.get("USDT", 0)))
                limits = api.get_symbol_limits(sym)
                funds_increment = Decimal(str(limits.get("minFunds", 0.01))) if limits else Decimal("0.01")
                per_pos = min(
                    usdt * MAX_POSITION_RATIO,
                    usdt / max(1, len(top_syms_pair))
                )
                rounded_amt = (Decimal(per_pos) // funds_increment) * funds_increment
                rounded_amt = rounded_amt.quantize(funds_increment, rounding=ROUND_DOWN)
                if usdt < funds_increment:
                    log_info(f"  - {sym} 可用资金 {usdt} 不足minFunds={funds_increment}，无法买入。")
                elif rounded_amt < funds_increment:
                    log_info(
                        f"  - {sym} 可买金额 {rounded_amt} 不足步进要求（minFunds={funds_increment}），"
                        f"资金: USDT={usdt}, MAX_POSITION_RATIO={MAX_POSITION_RATIO}, topN={len(top_syms_pair)}"
                    )
                else:
                    log_info(f"  - {sym} 其它未知原因（持仓已存在？）")