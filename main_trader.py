import time
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
    )
    print("[系统] 运行于【真实KuCoin账户】模式，所有资金与持仓为实盘。")

from strategy import score_symbols
from notifier import send_serverchan_notification  # <- 必须用这个名字

def main():
    start_time = time.time()
    # 1. 获取可交易币种列表与评分
    top_symbols = score_symbols()
    print(f"\n[主控] 本轮Top评分币种: {top_symbols[:5]}")

    # 2. 读取当前账户持仓&余额
    balances = get_account_balances()
    positions = get_positions()
    print(f"[主控] 当前账户余额: {balances}")
    print(f"[主控] 当前虚拟持仓: {positions}")

    # 3. 卖出触发卖点的币（可直接调用rebalancer逻辑）
    from rebalancer import rebalance_portfolio
    rebalance_portfolio(
        top_symbols=top_symbols,
        balances=balances,
        positions=positions,
        place_order=place_order
    )

    # 4. 示例推送（如需要，可以取消注释）
    # send_serverchan_notification("本轮调仓报告", report_content)

    elapsed = time.time() - start_time
    print(f"[主控] 本轮运行完成，耗时{elapsed:.2f}秒")

if __name__ == "__main__":
    main()