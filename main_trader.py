import time
import concurrent.futures
from config import CONFIG, LOG_DIR
from strategy import get_symbol_score
from notifier import send_serverchan_notification
from rebalancer import rebalance_portfolio, get_blacklist, is_symbol_in_cooldown
from kucoin_api import KuCoinClient

DEFAULT_WORKERS = 10
MIN_TURNOVER_1H = CONFIG.get("MIN_TURNOVER_1H", 5000)

def fetch_score(symbol, sleep_time=0.18):
    try:
        time.sleep(sleep_time)
        score_data = get_symbol_score(symbol)
        return symbol, score_data.get("score", 0), score_data.get("turnover", 0)
    except Exception as e:
        print(f"[WARN] 获取 {symbol} 评分失败: {e}")
        return symbol, -999, 0

def main():
    start_time = time.time()
    api = KuCoinClient()

    if CONFIG["SIMULATE"]:
        from sim_account import (
            sim_get_balance as get_account_balances,
            sim_get_positions as get_positions,
            sim_place_order as place_order,
        )
        print("[系统] 运行于【本地模拟账户】模式。")
    else:
        print("[系统] 运行于【真实KuCoin账户】模式。")
        get_account_balances = api.get_account_holdings
        get_positions = api.get_account_holdings
        place_order = api.place_order

    all_symbols = api.get_supported_symbols()
    print(f"[主控] 共获取到 {len(all_symbols)} 个交易对，开始多线程评分...")

    max_workers = CONFIG.get("MAX_WORKERS", DEFAULT_WORKERS)
    sleep_time = CONFIG.get("WORKER_SLEEP", 0.18)
    all_scores = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        results = list(executor.map(lambda sym: fetch_score(sym, sleep_time), all_symbols))

    filtered_scores = {}
    for symbol, score, turnover in results:
        if turnover < MIN_TURNOVER_1H:
            print(f"[过滤] {symbol} 最近1小时成交额 {turnover:.2f} USDT < {MIN_TURNOVER_1H}，剔除")
            continue
        if symbol in get_blacklist():
            print(f"[过滤] {symbol} 在黑名单中，剔除")
            continue
        if is_symbol_in_cooldown(symbol):
            print(f"[过滤] {symbol} 正在冷却中，剔除")
            continue
        filtered_scores[symbol] = score

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

    rebalance_portfolio(
        top_symbols=top_symbols,
        balances=balances,
        positions=positions,
        place_order=place_order
    )

    elapsed = time.time() - start_time
    print(f"[主控] 本轮运行完成，耗时{elapsed:.2f}秒")

if __name__ == "__main__":
    main()