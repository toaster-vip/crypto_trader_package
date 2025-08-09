# rebalancer.py（仅展示修改点，整文件你可直接覆盖）
# ...
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

    # === 新增：本轮汇总 ===
    summary = {
        "sells": [],      # {symbol, amount, entry, price, pnl_pct, reason, cooldown_until}
        "buys": [],       # {symbol, funds, price, orderid}
        "holds": [],      # 仅在 LOG_DETAIL=True 时填充，减少通知长度
        "cooldown_updates": [],  # {symbol, until}
        "notes": [],      # 异常/告警统计
    }

    # 1. 买前快照
    print_snapshot(api, tag="买入/卖出前", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices() or {}

    usdt = Decimal(str(balances.get("USDT", 0)))
    cur_hold = {to_symbol_pair(k): v for k, v in positions.items() if get_amount(v) > 0}

    total_asset = usdt + sum(
        get_dynamic_entry_price(k, v, entry_price_state, api=api) * get_amount(v)
        for k, v in cur_hold.items()
    )
    _ = min(total_asset * MAX_POSITION_RATIO, usdt / max(1, len(top_syms_pair))) if top_syms_pair else Decimal("0")

    sold_count = 0
    for symbol, pos in cur_hold.items():
        sym = to_symbol_pair(symbol)
        amount = get_amount(pos)
        entry = get_dynamic_entry_price(sym, pos, entry_price_state, api=api)
        cur_price_raw = all_prices.get(sym, None) or api.get_symbol_price(sym)
        if cur_price_raw is None:
            log_info(f"[跳过] {sym} 无法获取当前价格，跳过卖出/持有决策。")
            summary["notes"].append(f"{sym}: 无价跳过")
            continue
        cur_price = Decimal(str(cur_price_raw))

        if entry <= 0:
            log_info(f"[警告] {sym} 缺少有效买入价（entry<=0），已跳过卖出/止损/止盈决策。")
            summary["notes"].append(f"{sym}: entry<=0")
            continue

        pnl = (cur_price - entry) / (entry + Decimal('1e-8'))

        if pnl <= STOP_LOSS:
            if not dry_run:
                place_order('sell', sym, float(amount))
                cooldown_pool[sym] = current_round + cooldown_rounds
                entry_price_state.pop(sym, None)
            log_info(f"[止损] {sym} 触发止损并冷却{cooldown_rounds}轮 | 买入价={entry} | 当前价={cur_price} | 盈亏={pnl:.4%}")
            sold_count += 1
            summary["sells"].append({
                "symbol": sym,
                "amount": float(amount),
                "entry": float(entry),
                "price": float(cur_price),
                "pnl_pct": float(pnl),
                "reason": "STOP_LOSS",
                "cooldown_until": int(cooldown_pool.get(sym, current_round))
            })
            summary["cooldown_updates"].append({"symbol": sym, "until": int(cooldown_pool.get(sym, current_round))})
            continue

        if sym in top_syms_pair and pnl >= TAKE_PROFIT:
            entry_price_state[sym] = float(cur_price)
            log_info(f"[动态止盈] {sym} 达止盈线且仍在TopN，上移entry至 {cur_price} | 原entry: {entry} | 盈亏={pnl:.4%}")
        else:
            if CONFIG.get("LOG_DETAIL", True):
                log_info(f"[持有] {sym} | entry={entry} | cur={cur_price} | pnl={pnl:.4%}")
                summary["holds"].append({
                    "symbol": sym,
                    "amount": float(amount),
                    "price": float(cur_price),
                    "entry": float(entry),
                    "pnl_pct": float(pnl),
                })

    # 卖出后快照
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
    all_prices = api.get_all_prices() or {}
    print_snapshot(api, tag="卖出后", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    # 买入
    buy_count = 0
    balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
    usdt = Decimal(str(balances.get("USDT", 0)))
    minfunds_fallback = Decimal(str(MIN_BUY_AMOUNT))
    top_count = max(1, len(top_syms_pair)) if top_syms_pair else 0
    per_pos_usdt = min(usdt * MAX_POSITION_RATIO, usdt / top_count) if top_count else Decimal("0")

    for symbol in top_syms_pair:
        sym = to_symbol_pair(symbol)
        cooldown = cooldown_pool.get(sym, 0)
        if cooldown > current_round:
            if CONFIG.get("LOG_DETAIL", True):
                log_info(f"[冷却中] {sym} 剩余{cooldown-current_round}轮，跳过。")
            continue

        positions = api.get_positions(simulate=CONFIG.get("SIMULATE", False))
        hold_syms = set(to_symbol_pair(k) for k in positions.keys() if get_amount(positions[k]) > 0)
        if sym in hold_syms:
            continue

        limits = api.get_symbol_limits(sym) or {}
        funds_increment = Decimal(str(limits.get("minFunds", minfunds_fallback)))

        rounded_amt = (Decimal(per_pos_usdt) // funds_increment) * funds_increment
        rounded_amt = rounded_amt.quantize(funds_increment, rounding=ROUND_DOWN)

        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))
        if usdt < funds_increment or rounded_amt < funds_increment:
            if CONFIG.get("LOG_DETAIL", True):
                log_info(f"[跳过] {sym} 可买金额{rounded_amt} 或余额{usdt} 不足 minFunds={funds_increment}。")
            continue

        log_info(f"[买入] {sym} 金额: {rounded_amt:.8f}")
        orderid = None
        entry_price = None
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

        summary["buys"].append({
            "symbol": sym,
            "funds": float(rounded_amt),
            "price": float(entry_price) if entry_price is not None else None,
            "orderid": orderid
        })

        balances = api.get_balances(simulate=CONFIG.get("SIMULATE", False))
        usdt = Decimal(str(balances.get("USDT", 0)))
        remaining_slots = max(1, (top_count - buy_count)) if top_count else 1
        per_pos_usdt = min(usdt * MAX_POSITION_RATIO, usdt / remaining_slots)

    print_snapshot(api, tag="买入后", extra_syms=top_syms_pair)
    print_cooldown_pool(cooldown_pool, current_round)

    save_entry_price_state(entry_price_state)
    save_cooldown_pool(cooldown_pool)

    log_info("[调仓结束]")
    if sold_count == 0:
        log_info("本轮未发生卖出。")
    if buy_count == 0 and top_syms_pair:
        log_info("本轮未发生买入（可能因冷却/余额/步进限制）。")

    return summary