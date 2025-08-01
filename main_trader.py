import time
import concurrent.futures
import threading
from config import CONFIG, LOG_DIR
from strategy import get_symbol_score
from notifier import send_serverchan_notification
from rebalancer import rebalance_portfolio, get_blacklist, is_symbol_in_cooldown
from kucoin_api import KuCoinClient
import requests

DEFAULT_WORKERS = 10
MIN_TURNOVER_1H = CONFIG.get("MIN_TURNOVER_1H", 5000)
progress_counter = {"done": 0}

def fetch_score(symbol, sleep_time=0.18):
    try:
        time.sleep(sleep_time)
        score_data = get_symbol_score(symbol)
        return symbol, score_data.get("score", 0), score_data.get("turnover", 0)
    except Exception as e:
        print(f"[WARN] 获取 {symbol} 评分失败: {e}")
        return symbol, -999, 0
    finally:
        progress_counter["done"] += 1

def get_all_tickers(api):
    url = api.base_url + "/api/v1/market/allTickers"
    try:
        resp = api.session.get(url) if hasattr(api, "session") else requests.get(url)
        data = resp.json()
        ticker_map = {}
        for item in data.get("data", {}).get("ticker", []):
            last = item.get("last")
            symbol = item.get("symbol")
            if last is not None and symbol:
                try:
                    ticker_map[symbol] = float(last)
                except Exception:
                    pass
        return ticker_map
    except Exception as e:
        print(f"[ERROR] 批量获取ticker失败: {e}")
        return {}

def progress_watcher(total):
    last_print = -1
    while progress_counter["done"] < total:
        if progress_counter["done"] != last_print:
            print(f"[进度] 已完成 {progress_counter['done']}/{total} 个币种评分...")
            last_print = progress_counter["done"]
        time.sleep(10)
    print(f"[进度] 已全部完成：{total}/{total}")

def get_portfolio_stats(positions, price_map):
    total_value = 0
    total_cost = 0
    details = []
    for symbol, pos in positions.items():
        amount = float(pos.get("amount", 0))
        entry_price = float(pos.get("entry_price", 0))
        price = float(price_map.get(symbol, entry_price))
        value = amount * price
        cost = amount * entry_price
        total_value += value
        total_cost += cost
        details.append((symbol, amount, entry_price, price, value, cost))
    return total_value, total_cost, details

def main():
    start_time = time.time()
    api = KuCoinClient()

    if CONFIG.get("SIMULATE"):
        from sim_account import (
            sim_get_balance as get_account_balances,
            sim_get_positions as get_positions,
            sim_place_order as sim_place_order_raw,
        )
        print("[系统] 运行于【本地模拟账户】模式。")
    else:
        print("[系统] 运行于【真实KuCoin账户】模式。")
        get_account_balances = api.get_account_holdings
        get_positions = api.get_account_holdings
        place_order = api.place_order

    all_symbols = api.get_supported_symbols()
    total = len(all_symbols)
    print(f"[主控] 共获取到 {total} 个交易对，开始多线程评分...")

    max_workers = CONFIG.get("MAX_WORKERS", DEFAULT_WORKERS)
    sleep_time = CONFIG.get("WORKER_SLEEP", 0.18)

    price_map = get_all_tickers(api)

    progress_counter["done"] = 0
    progress_thread = threading.Thread(target=progress_watcher, args=(total,))
    progress_thread.daemon = True
    progress_thread.start()

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(lambda sym: fetch_score(sym, sleep_time), all_symbols))

    progress_thread.join()

    filtered_scores = {}
    turnover_filtered = 0
    blacklist_filtered = 0
    cooldown_filtered = 0

    for symbol, score, turnover in results:
        if turnover < MIN_TURNOVER_1H:
            turnover_filtered += 1
            continue
        if symbol in get_blacklist():
            blacklist_filtered += 1
            continue
        if is_symbol_in_cooldown(symbol):
            cooldown_filtered += 1
            continue
        filtered_scores[symbol] = score

    print(f"[过滤] 本轮共 {turnover_filtered}/{total} 个币种因成交额不足 {MIN_TURNOVER_1H} USDT 被过滤。")
    print(f"[过滤] 本轮共 {blacklist_filtered}/{total} 个币种因黑名单被过滤。")
    print(f"[过滤] 本轮共 {cooldown_filtered}/{total} 个币种因冷却期被过滤。")
    print(f"[过滤] 本轮剩余 {len(filtered_scores)}/{total} 个币种进入下一轮筛选。")

    if not filtered_scores:
        print("[主控] ⚠️ 没有可用的币种（全部被过滤）。")
        return

    top_n = CONFIG.get("TOP_N", 5)
    top_symbols = sorted(filtered_scores, key=filtered_scores.get, reverse=True)[:top_n]
    print(f"\n[主控] 本轮Top评分币种（已过滤）: {top_symbols}")

    balances = get_account_balances()
    positions = get_positions()
    print(f"[主控] 当前账户余额: {balances}")
    print(f"[主控] 当前虚拟持仓: {positions}")

    # --- 汇总资产并打印 ---
    total_value, total_cost, details = get_portfolio_stats(positions, price_map)
    print(f"[主控] 持仓总市值：{total_value:.2f} USDT，持仓成本：{total_cost:.2f} USDT，浮盈亏：{total_value-total_cost:.2f} USDT")
    for sym, amt, entry, price, val, cost in details:
        print(f"   - {sym}: 数量{amt:.4f}, 买入{entry}, 现价{price}, 市值{val:.2f}, 盈亏{val-cost:.2f}")

    # ------ 关键：模拟盘下单始终用市价 --------
    if CONFIG.get("SIMULATE"):
        def place_order(side, symbol, amount, price=None, now_time=None):
            # price_map是最新市价映射
            return sim_place_order_raw(
                side, symbol, amount, price, now_time,
                market_price=price_map.get(symbol)
            )
    # ------------------------------------------

    rebalance_portfolio(
        top_symbols=top_symbols,
        balances=balances,
        positions=positions,
        place_order=place_order,
        price_map=price_map
    )

    elapsed = time.time() - start_time
    print(f"[主控] 本轮运行完成，耗时{elapsed:.2f}秒")

if __name__ == "__main__":
    main()