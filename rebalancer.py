import time
import json
import os
from decimal import Decimal, ROUND_DOWN
from config import CONFIG
from log_utils import log_info, log_debug, log_trade_detail
from kucoin_api import to_symbol_pair

ENTRY_PRICE_FILE = CONFIG.get("ENTRY_PRICE_FILE", "entry_price_state.json")
COOLDOWN_FILE = CONFIG.get("COOLDOWN_FILE", "cooldown_pool.json")

def load_json_file(filepath, default=None):
    if os.path.exists(filepath):
        with open(filepath, "r") as f:
            return json.load(f)
    return default or {}

def save_json_file(filepath, data):
    with open(filepath, "w") as f:
        json.dump(data, f)

def get_amount(pos):
    return Decimal(str(pos.get("amount", 0))) if isinstance(pos, dict) else Decimal("0")

def get_entry_price(symbol, pos, entry_price_state, api):
    sym = to_symbol_pair(symbol)
    entry = entry_price_state.get(sym)
    if entry and float(entry) > 0:
        return Decimal(str(entry))
    # 尝试通过持仓或成交填充
    fills = api.get_fills(sym, side="buy")
    total_amt = sum(float(f.get("size", 0)) for f in fills if float(f.get("size", 0)) > 0)
    total_cost = sum(float(f.get("size", 0)) * float(f.get("price", 0)) for f in fills)
    if total_amt > 0:
        return Decimal(str(total_cost / total_amt))
    return Decimal("0")

def rebalance_portfolio(
    top_symbols,
    balances,
    positions,
    place_order,
    price_map,
    dry_run=False,
    api=None,
    cooldown_pool=None,
    current_round=None,
    cooldown_rounds=None
):
    assert api is not None, "必须传入 api"
    entry_price_state = load_json_file(ENTRY_PRICE_FILE, {})
    cooldown_pool = cooldown_pool or load_json_file(COOLDOWN_FILE, {})
    current_round = current_round or int(time.time() // (3600 * 4))
    cooldown_rounds = cooldown_rounds or CONFIG.get("COOLDOWN_ROUNDS", 3)

    MAX_RATIO = Decimal(str(CONFIG["MAX_POSITION_RATIO"]))
    TAKE_PROFIT = Decimal(str(CONFIG["TAKE_PROFIT"]))
    STOP_LOSS = Decimal(str(CONFIG["STOP_LOSS"]))
    MIN_BUY = Decimal(str(CONFIG["MIN_BUY_AMOUNT"]))

    all_prices = api.get_all_prices()
    top_syms = [to_symbol_pair(s) for s in top_symbols]

    usdt = Decimal(str(balances.get("USDT", 0)))
    hold_syms = {to_symbol_pair(s): v for s, v in positions.items()}
    total_value = usdt + sum(
        get_amount(pos) * Decimal(str(all_prices.get(sym, 0))) for sym, pos in hold_syms.items()
    )
    per_alloc = total_value * MAX_RATIO if total_value > 0 else Decimal("0")

    log_info(f"\n✅ 本轮 TopN: {top_syms}")
    log_info(f"💰 当前 USDT: {usdt:.4f}，最大单币投入: {per_alloc:.4f}")

    # ========== Step 1. 卖出 ==========
    sold = 0
    for sym, pos in hold_syms.items():
        if sym not in all_prices:
            log_info(f"[跳过] {sym} 无法获取价格")
            continue
        cur_price = Decimal(str(all_prices[sym]))
        entry = get_entry_price(sym, pos, entry_price_state, api)
        pnl = (cur_price - entry) / (entry + Decimal("1e-8")) if entry > 0 else Decimal("0")
        amt = get_amount(pos)

        # 止盈止损逻辑
        reason = None
        if pnl <= STOP_LOSS:
            reason = "止损"
        elif pnl >= TAKE_PROFIT and sym not in top_syms:
            reason = "止盈"

        if reason:
            log_info(f"[{reason}] {sym} | 价格: {cur_price:.4f} | 盈亏: {pnl:.2%}")
            if not dry_run:
                place_order("sell", sym, float(amt))
                cooldown_pool[sym] = current_round + cooldown_rounds
                entry_price_state.pop(sym, None)
            sold += 1
        else:
            log_info(f"[持仓] {sym} | 价格: {cur_price:.4f} | 盈亏: {pnl:.2%} | 状态: 持有")

    # ========== Step 2. 买入 ==========
    bought = 0
    for sym in top_syms:
        if cooldown_pool.get(sym, 0) > current_round:
            log_info(f"[冷却] {sym} 跳过")
            continue
        if sym in hold_syms:
            log_info(f"[跳过] {sym} 已持有")
            continue

        price = Decimal(str(all_prices.get(sym, 0)))
        limit = api.get_symbol_limits(sym)
        min_fund = Decimal(str(limit.get("minFunds", 0.1))) if limit else Decimal("0.1")

        amount = min(per_alloc, usdt)
        if amount < min_fund:
            log_info(f"[跳过] {sym} 资金不足（{amount:.4f} < min {min_fund}）")
            continue

        log_info(f"[买入] {sym} 金额: {amount:.4f}")
        if not dry_run:
            place_order("buy", sym, float(amount))
            entry_price = api.get_symbol_price(sym)
            if entry_price:
                entry_price_state[sym] = float(entry_price)
        bought += 1
        usdt -= amount

    if sold == 0:
        log_info("本轮未卖出")
    if bought == 0:
        log_info("本轮未买入")

    # ========== Step 3. 保存状态 ==========
    save_json_file(ENTRY_PRICE_FILE, entry_price_state)
    save_json_file(COOLDOWN_FILE, cooldown_pool)