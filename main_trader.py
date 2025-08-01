import time
import concurrent.futures
from config import CONFIG, LOG_DIR
import logging
from strategy import get_symbol_score
from notifier import send_serverchan_notification
from rebalancer import rebalance_portfolio
from kucoin_api import KuCoinClient

DEFAULT_WORKERS = 10

def fetch_score(symbol, sleep_time=0.18):
    """单币评分线程入口，sleep可调节吞吐"""
    try:
        time.sleep(sleep_time)  # 每线程小延迟，防爆发
        score_data = get_symbol_score(symbol)
        if isinstance(score_data, dict):
            return symbol, score_data["score"]
        else:
            return symbol, score_data
    except Exception as e:
        print(f"[WARN] 获取 {symbol} 评分失败: {e}")
        return symbol, -999

def main():
    start_time = time.time()
    api = KuCoinClient()  # 实例化API对象

    if CONFIG["SIMULATE"]:
        from sim_account import (
            sim_get_balance as get_account_balances,
            sim_get_positions as get_positions,
            sim_place_order as place_order,
        )
        print("[系统] 运行于【本地模拟账户】模式，所有资金与持仓均仅本地模拟。")
    else:
        print("[系统] 运行于【真实KuCoin账户】模式，所有资金与持仓为实盘。")
        get_account_balances = api.get_account_holdings
        get_positions = api.get_account_holdings
        place_order = api.place_order

    # 自动获取所有支持的USDT币对
    all_symbols = api.get_supported_symbols()
    print(f"[主控] 共获取到 {len(all_symbols)} 个交易对，开始多线程评分...")

    max_workers = CONFIG.get("MAX_WORKERS", DEFAULT_WORKERS)
    sleep_time = CONFIG.get("WORKER_SLEEP", 0.18)
    all_scores = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        # 注意：用 map 自动按照顺序返回结果，不用as_completed遍历
        results = list(executor.map(lambda sym: fetch_score(sym, sleep_time), all_symbols))

    # 组装结果
    for symbol, score in results:
        all_scores[symbol] = score

    top_n = CONFIG.get("TOP_N", 5)
    top_symbols = sorted(all_scores, key=all_scores.get, reverse=True)[:top_n]
    print(f"\n[主控] 本轮Top评分币种: {top_symbols}")

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