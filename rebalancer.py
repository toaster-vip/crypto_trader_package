import time
from decimal import Decimal
from config import CONFIG
from log_utils import log_info, log_trade_detail
from kucoin_api import to_symbol_pair

TAKE_PROFIT = Decimal(str(CONFIG["TAKE_PROFIT"]))
STOP_LOSS = Decimal(str(CONFIG["STOP_LOSS"]))
TRAILING_STOP_PCT = Decimal(str(CONFIG["TRAILING_STOP_PCT"]))
MAX_POSITION_RATIO = Decimal(str(CONFIG["MAX_POSITION_RATIO"]))
MIN_BUY_AMOUNT = Decimal(str(CONFIG["MIN_BUY_AMOUNT"]))

def rebalance_portfolio(top_symbols, balances, positions, place_order, price_map=None, dry_run=False, api=None):
    if api is None:
        raise ValueError("必须传入唯一的 KuCoinClient api 实例！（请主控调用时用 api=api 传入）")
    log_info(f"== 调仓轮 == Top池: {top_symbols}")
    usdt = Decimal(str(balances.get("USDT", 0)))
    cur_hold = {to_symbol_pair(k): v for k, v in positions.items() if get_amount(v) > 0}
    hold_syms = set(cur_hold.keys())
    top_syms_pair = [to_symbol_pair(s) for s in top_symbols]
    total_asset = usdt + sum(get_entry_price(pos) * get_amount(pos) for pos in cur_hold.values())
    per_pos = min(total_asset * MAX_POSITION_RATIO, usdt / max(1, len(top_syms_pair))) if top_syms_pair else Decimal("0")

    for symbol, pos in cur_hold.items():
        entry = get_entry_price(pos)
        amount = get_amount(pos)
        if price_map and symbol in price_map:
            cur_price = Decimal(str(price_map[symbol]))
        else:
            cur_price = Decimal(str(api.get_symbol_price(symbol)))
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

    # 新热点补仓
    for symbol in top_syms_pair:
        if symbol not in hold_syms and per_pos >= MIN_BUY_AMOUNT and usdt >= per_pos:
            log_info(f"[买入] {symbol} 买入金额: {float(per_pos):.2f}")
            if not dry_run:
                place_order('buy', symbol, float(per_pos))
            usdt -= per_pos
            if price_map and symbol in price_map:
                buy_price = float(price_map[symbol])
            else:
                buy_price = float(api.get_symbol_price(symbol))
            log_trade_detail({
                "type": "buy",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "symbol": symbol,
                "amount": float(per_pos),
                "price": buy_price,
            })
    log_info("[调仓结束]")