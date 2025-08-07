# rebalancer.py
import time
import json
import os
from decimal import Decimal, ROUND_DOWN
from config import CONFIG
from log_utils import log_info, log_trade_detail
from kucoin_api import to_symbol_pair

# ====== Entry Price 本地状态存储 ======
ENTRY_PRICE_FILE = "/home/linuxuser/crypto_trader_package/entry_price_state.json"

def load_entry_price_state():
    if os.path.exists(ENTRY_PRICE_FILE):
        with open(ENTRY_PRICE_FILE, "r") as f:
            return json.load(f)
    return {}

def save_entry_price_state(state):
    with open(ENTRY_PRICE_FILE, "w") as f:
        json.dump(state, f)

def get_dynamic_entry_price(symbol, pos, entry_price_state):
    sym = to_symbol_pair(symbol)
    if sym in entry_price_state:
        return Decimal(str(entry_price_state[sym]))
    return Decimal(str(pos.get("entry_price", 0)))

# ====== 其余参数 ======
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

def rebalance_portfolio(
    top_symbols, balances, positions, place_order,
    price_map=None, dry_run=False, api=None,
    cooldown_pool=None, current_round=None, cooldown_rounds=COOLDOWN_ROUNDS
):
    """
    主调仓函数：支持冷却池和动态entry price
    """
    if api is None:
        raise ValueError("必须传入唯一的 KuCoinClient api 实例！（主控请用 rebalance_portfolio(..., api=api)）")
    if cooldown_pool is None:
        cooldown_pool = {}
    if current_round is None:
        current_round = int(time.time() // (3600 * 4))

    entry_price_state = load_entry_price_state()

    log_info(f"== 调仓轮 == Top池: {top_symbols}")
    usdt = Decimal(str(balances.get("USDT", 0)))
    cur_hold = {to_symbol_pair(k): v for k, v in positions.items() if get_amount(v) > 0}
    hold_syms = set(cur_hold.keys())
    top_syms_pair = [to_symbol_pair(s) for s in top_symbols]
    total_asset = usdt + sum(get_dynamic_entry_price(k, v, entry_price_state) * get_amount(v) for k, v in cur_hold.items())
    per_pos = min(total_asset * MAX_POSITION_RATIO, usdt / max(1, len(top_syms_pair))) if top_syms_pair else Decimal("0")

    # ========== 1. 卖出/动态止盈 ==========
    for symbol, pos in cur_hold.items():
        sym = to_symbol_pair(symbol)
        amount = get_amount(pos)
        entry = get_dynamic_entry_price(sym, pos, entry_price_state)
        # 取最新价
        if price_map and sym in price_map:
            cur_price_raw = price_map[sym]
        else:
            cur_price_raw = api.get_symbol_price(sym)
        if cur_price_raw is None:
            log_info(f"[跳过] {sym} 无法获取当前价格，自动跳过卖出/持有决策！")
            continue
        cur_price = Decimal(str(cur_price_raw))
        pnl = (cur_price - entry) / (entry + Decimal('1e-8'))

        # ---- 止损，强制卖出并冷却，清理entry price
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
            log_info(f"[止损] {sym} 触发止损，卖出并冷却{cooldown_rounds}轮")
            continue

        # ---- 动态止盈，如果还在TopN，只更新成本价，不卖
        if sym in top_syms_pair and pnl >= TAKE_PROFIT:
            entry_price_state[sym] = float(cur_price)
            log_info(f"[动态止盈] {sym} 达到止盈线且仍为TopN，动态上移entry price: {cur_price}")
            continue

        # ---- 如果不在Top池且也没触发止损止盈，续持
        if sym not in top_syms_pair:
            log_info(f"[续持] {sym} 非热点但未触发止盈止损，留仓")
        else:
            log_info(f"[持有] {sym} 正常持有")

    # ========== 2. 卖出后刷新usdt余额 ==========
    if not dry_run:
        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))

    # ========== 3. 新热点买入 ==========
    for symbol in top_syms_pair:
        sym = to_symbol_pair(symbol)
        # 冷却池过滤
        if cooldown_pool and cooldown_pool.get(sym, 0) > current_round:
            log_info(f"[冷却中] {sym} 在冷却期，跳过买入。")
            continue

        if sym not in hold_syms and per_pos >= MIN_BUY_AMOUNT and usdt >= per_pos:
            limits = api.get_symbol_limits(sym)
            funds_increment = Decimal(str(limits.get("minFunds", 0.01))) if limits else Decimal("0.01")
            rounded_amt = (per_pos // funds_increment) * funds_increment
            rounded_amt = rounded_amt.quantize(funds_increment, rounding=ROUND_DOWN)
            if rounded_amt < funds_increment:
                log_info(f"[跳过] {sym} 可买金额不足步进要求（minFunds={funds_increment}），跳过！")
                continue
            log_info(f"[买入] {sym} 买入金额: {rounded_amt:.8f}")
            if not dry_run:
                place_order('buy', sym, float(rounded_amt))
                # 买入时记录新 entry price
                entry_price = api.get_symbol_price(sym)
                if entry_price is not None:
                    entry_price_state[sym] = float(entry_price)
            usdt -= rounded_amt
            if price_map and sym in price_map:
                buy_price = float(price_map[sym])
            else:
                buy_price_raw = api.get_symbol_price(sym)
                if buy_price_raw is None:
                    log_info(f"[跳过] {sym} 买入时无法获价，跳过！")
                    continue
                buy_price = float(buy_price_raw)
            log_trade_detail({
                "type": "buy",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": sym,
                "amount": float(rounded_amt),
                "price": buy_price,
            })

    # ========== 4. 持久化entry price ==========
    save_entry_price_state(entry_price_state)
    log_info("[调仓结束]")