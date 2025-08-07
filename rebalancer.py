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

def rebalance_portfolio(top_symbols, balances, positions, place_order, price_map=None, dry_run=False, api=None):
    """
    调仓逻辑（兼容多币种/主流量化风格）。
    :param api: 必传唯一 KuCoinClient 实例（主控层全局只初始化一次）
    """
    if api is None:
        raise ValueError("必须传入唯一的 KuCoinClient api 实例！（主控请用 rebalance_portfolio(..., api=api)）")

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
            log_info(f"[平仓] {symbol} 触发止盈止损")
        elif symbol not in top_syms_pair:
            log_info(f"[续持] {symbol} 非热点但未触发止盈止损，留仓")
        elif pnl >= TAKE_PROFIT:
            trade["reason"] = "TAKE_PROFIT"
            log_trade_detail(trade)
            if not dry_run:
                place_order('sell', symbol, float(amount))
            log_info(f"[止盈] {symbol} 达到止盈")
        elif pnl <= STOP_LOSS:
            trade["reason"] = "STOP_LOSS"
            log_trade_detail(trade)
            if not dry_run:
                place_order('sell', symbol, float(amount))
            log_info(f"[止损] {symbol} 触发止损")
        else:
            log_info(f"[持有] {symbol} 正常持有")

    # ========== 2. 卖出后刷新usdt余额（实盘/模拟自动切换） ==========
    if not dry_run:
        # 注意：如有并发或其它进程下单，建议加重试
        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))

    # ========== 3. 新热点买入（按步进修正，确保主流所合规） ==========
    for symbol in top_syms_pair:
        if symbol not in hold_syms and per_pos >= MIN_BUY_AMOUNT and usdt >= per_pos:
            # 步进修正（decimal更精确，确保不会increment invalid）
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