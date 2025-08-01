def rebalance_portfolio(top_symbols, balances, positions, place_order, price_map=None):
    print("\n🔁 [调仓] 开始执行智能调仓逻辑")
    api = KuCoinClient()
    is_simulate = CONFIG.get("SIMULATE", True)
    raw_usdt = Decimal(str(balances.get("USDT", 0)))
    usdt_total = Decimal(str(CONFIG.get("SIM_START_BALANCE", 100))) if is_simulate else raw_usdt
    usdt_avail = raw_usdt

    positions = {k: v for k, v in positions.items() if Decimal(str(v.get("amount", 0))) > 0}
    print("🪙 当前持仓市值与成本：")
    hold_total_cost, hold_total_value = Decimal("0"), Decimal("0")
    for symbol, pos in positions.items():
        entry = Decimal(str(pos.get("entry_price", 0)))
        amount = Decimal(str(pos.get("amount", 0)))
        cost = entry * amount
        cur_price = get_price_with_map(symbol, price_map, api)
        value = (cur_price or Decimal("0")) * amount
        pnl_pct = ((value - cost) / cost * 100) if cost > 0 else Decimal("0")
        print(f" - {symbol:>12}: 持仓 {amount:.4f}，买入成本 {cost:.2f}，现价市值 {value:.2f}，盈亏 {pnl_pct:.2f}%")
        hold_total_cost += cost
        hold_total_value += value
    print(f"📊 持仓总成本: {hold_total_cost:.2f}，现价总市值: {hold_total_value:.2f}，盈亏 {((hold_total_value-hold_total_cost)/hold_total_cost*100) if hold_total_cost else 0:.2f}%\n")

    sell_list = []
    now = time.strftime('%Y-%m-%d %H:%M:%S')
    for symbol, pos in positions.items():
        try:
            entry = Decimal(str(pos.get("entry_price", 0)))
            amount = Decimal(str(pos.get("amount", 0)))
        except Exception as e:
            print(f"[异常] 解析持仓数据失败 {symbol}: {e}")
            continue
        current_price = get_price_with_map(symbol, price_map, api)
        if entry is None or entry <= 0:
            continue
        if current_price is None or current_price <= 0:
            continue
        pnl_pct = (current_price - entry) / entry
        if pnl_pct >= TAKE_PROFIT:
            print(f"✅ 止盈：卖出 {symbol} 盈利 +{pnl_pct:.2%}")
            sell_list.append(symbol)
        elif pnl_pct <= STOP_LOSS:
            print(f"⛔ 止损：卖出 {symbol} 亏损 {pnl_pct:.2%}")
            sell_list.append(symbol)
            _symbol_buy_cooldown[symbol] = COOLDOWN_AFTER_LOSS
            _blacklist.add(symbol)
        elif symbol not in top_symbols:
            print(f"📉 排名跌出Top：卖出 {symbol}")
            sell_list.append(symbol)

    # === 执行卖出，详细打印成本和盈亏明细 ===
    for symbol in sell_list:
        pos = positions.get(symbol)
        if not pos:
            continue
        entry_price = Decimal(str(pos.get("entry_price", 0)))
        amount = Decimal(str(pos.get("amount", 0)))
        cur_price = get_price_with_map(symbol, price_map, api)
        cost = entry_price * amount
        value = (cur_price or Decimal("0")) * amount
        pnl = value - cost
        print(f"[调仓] ⚡ 卖出{symbol} - 持仓{amount:.8f} 买入总成本{cost:.8f} 卖出总额{value:.8f} 盈亏{pnl:.8f}")
        result = place_order("sell", symbol, float(amount), None, now_time=now)
        if result:
            print(f"[调仓] ✅ 卖出 {symbol} 成功")
        else:
            print(f"[调仓] ❌ 卖出 {symbol} 失败")

    if not is_simulate:
        usdt_avail = Decimal(str(balances.get("USDT", 0)))
    print("\n[调仓] 卖出后账户快照：")
    print(f"  - 可用USDT: {usdt_avail:.2f}")
    for symbol in sell_list:
        positions.pop(symbol, None)
    hold_total_value = Decimal("0")
    for symbol, pos in positions.items():
        cur_price = get_price_with_map(symbol, price_map, api)
        if cur_price:
            hold_total_value += cur_price * Decimal(str(pos.get("amount", 0)))
    print(f"  - 持仓币种市值合计: {hold_total_value:.2f}\n")

    cur_holding_count = len([s for s in positions if Decimal(str(positions[s].get("amount", 0))) > 0])
    max_hold_count = CONFIG.get("MAX_HOLD_COUNT", 6)
    remain_slots = max_hold_count - cur_holding_count
    reserve_ratio = Decimal(str(CONFIG.get("RESERVE_RATIO", 0.12)))
    min_buy_amount = Decimal(str(CONFIG.get("MIN_BUY_AMOUNT", 5)))
    fixed_buy_amount = Decimal(str(CONFIG.get("FIXED_BUY_AMOUNT", 10)))
    usdt_buyable = (usdt_avail * (Decimal("1") - reserve_ratio)).quantize(USDT_STEP, rounding=ROUND_DOWN)

    buy_count = 0
    for symbol in top_symbols:
        if remain_slots <= 0 or usdt_buyable < min_buy_amount:
            break
        if symbol in positions or symbol in _blacklist or _symbol_buy_cooldown.get(symbol, 0) > 0:
            continue

        max_alloc = (usdt_total * MAX_ALLOC_PER_SYMBOL).quantize(USDT_STEP, rounding=ROUND_DOWN)
        buy_amount = min(usdt_buyable / remain_slots, fixed_buy_amount, max_alloc)
        buy_amount = buy_amount.quantize(USDT_STEP, rounding=ROUND_DOWN)
        if buy_amount < min_buy_amount:
            print(f"[调仓] ⚠️ 资金不足跳过 {symbol}")
            continue

        cur_price = get_price_with_map(symbol, price_map, api)
        if not cur_price or cur_price <= 0:
            print(f"[调仓] ❗ 跳过 {symbol}（获取市价失败）")
            continue

        if is_simulate:
            buy_qty = (buy_amount / cur_price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
            result = place_order("buy", symbol, float(buy_qty), float(cur_price), now_time=now)
            print(f"[调仓] ✅ 买入 {symbol} 成功，金额 {buy_amount}，单价 {cur_price}，买入数量 {buy_qty}")
        else:
            result = place_order("buy", symbol, float(buy_amount), None, now_time=now)
            print(f"[调仓] ✅ 买入 {symbol} 成功，金额 {buy_amount}（市价买入，真实下单金额）")

        if result:
            usdt_buyable -= buy_amount
            buy_count += 1
            remain_slots -= 1
        else:
            print(f"[调仓] ❌ 买入 {symbol} 失败")

        if usdt_buyable < min_buy_amount:
            print(f"[调仓] 💸 余额耗尽，结束买入")
            break

    print("\n[调仓] 买入后账户快照：")
    print(f"  - 可用USDT: {usdt_buyable:.2f}")
    print(f"  - 持仓币种市值合计: {hold_total_value:.2f}\n")

    for s in list(_symbol_buy_cooldown.keys()):
        _symbol_buy_cooldown[s] -= 1
        if _symbol_buy_cooldown[s] <= 0:
            del _symbol_buy_cooldown[s]

    print(f"[调仓] ✅ 调仓结束，共买入 {buy_count} 个币种")