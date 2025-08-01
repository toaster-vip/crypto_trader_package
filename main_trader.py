from config import CONFIG, LOG_DIR
import logging

if CONFIG["SIMULATE"]:
    from sim_account import (
        sim_get_balance as get_account_balances,
        sim_get_positions as get_positions,
        sim_place_order as place_order,
    )
    print("[系统] 运行于【本地模拟账户】模式，所有资金与持仓均仅本地模拟。")
else:
    from kucoin_api import (
        get_trade_account_balances as get_account_balances,
        get_positions,
        place_order,
        get_supported_symbols
    )
    print("[系统] 运行于【真实KuCoin账户】模式，所有资金与持仓为实盘。")

from strategy import get_symbol_score
from notifier import send_serverchan_notification

def main():
    import time
    start_time = time.time()
    # 获取所有可用币种
    symbols = get_supported_symbols()
    # 对每个币种评分
    all_scores = {s: get_symbol_score(s) for s in symbols}
    # 排序取Top N
    top_symbols = sorted(all_scores, key=all_scores.get, reverse=True)[:5]
    print(f"\n[主控] 本轮Top评分币种: {top_symbols}")

    balances = get_account_balances()
    positions = get_positions()
    print(f"[主控] 当前账户余额: {balances}")
    print(f"[主控] 当前虚拟持仓: {positions}")

    from rebalancer import rebalance_portfolio
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