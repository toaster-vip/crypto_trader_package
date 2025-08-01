from config import CONFIG, LOG_DIR
import logging
from strategy import get_symbol_score
from notifier import send_serverchan_notification
from rebalancer import rebalance_portfolio
from kucoin_api import KuCoinClient

def main():
    import time
    start_time = time.time()

    api = KuCoinClient()  # 必须实例化

    if CONFIG["SIMULATE"]:
        from sim_account import (
            sim_get_balance as get_account_balances,
            sim_get_positions as get_positions,
            sim_place_order as place_order,
        )
        print("[系统] 运行于【本地模拟账户】模式，所有资金与持仓均仅本地模拟。")
        # 模拟模式下自定义币种池（可选）
        symbols = ["BTC-USDT", "ETH-USDT", "SOL-USDT", "DOGE-USDT"]
    else:
        print("[系统] 运行于【真实KuCoin账户】模式，所有资金与持仓为实盘。")
        # 通过 api 对象获取支持币种列表
        symbols = api.get_supported_symbols()
        get_account_balances = api.get_account_holdings
        get_positions = api.get_account_holdings
        place_order = api.place_order

    # 对每个币种打分
    all_scores = {}
    for s in symbols:
        score_data = get_symbol_score(s)
        if isinstance(score_data, dict):
            all_scores[s] = score_data["score"]
        else:
            all_scores[s] = score_data

    # 按分数排序取Top N
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