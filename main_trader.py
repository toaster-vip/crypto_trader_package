import time
import concurrent.futures
from config import CONFIG
from strategy import get_top_gainers_and_volume, get_symbol_score
from kucoin_api import KuCoinClient, to_symbol_pair
from rebalancer import rebalance_portfolio
from log_utils import log_snapshot, log_info, log_error

def fetch_score(api, symbol):
    try:
        score_obj = get_symbol_score(api, symbol)
        return symbol, score_obj
    except Exception as e:
        log_error(f"评分失败 {symbol}: {e}")
        return symbol, {"score": -999, "turnover": 0, "open": 0, "is_new_coin": True, "is_extreme": True}

def main():
    api = KuCoinClient()  # 全局只初始化一次
    hot_symbols = get_top_gainers_and_volume(api, top_n=CONFIG["HOT_TOP_N"])
    if not hot_symbols:
        log_error("本轮无热点币，暂停运行")
        return
    hot_symbols = [to_symbol_pair(s) for s in hot_symbols]
    log_info(f"本轮热点池: {hot_symbols}")

    # 多线程评分
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG["DEFAULT_WORKERS"]) as executor:
        futures = [executor.submit(fetch_score, api, s) for s in hot_symbols]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # 过滤
    symbol_scores = []
    for s, sc in results:
        if sc["turnover"] < CONFIG["MIN_TURNOVER_1H"]:
            continue
        if sc["is_extreme"]:
            continue
        symbol_scores.append((s, sc["score"], sc))
    symbol_scores.sort(key=lambda x: x[1], reverse=True)
    topN = CONFIG["TOP_N"]
    top_symbols = [x[0] for x in symbol_scores[:topN]]
    log_info(f"本轮选中TopN: {top_symbols}")

    # 资产快照前
    balances = api.get_balances(simulate=CONFIG["SIMULATE"])
    positions = api.get_positions(simulate=CONFIG["SIMULATE"])
    price_map = api.get_all_prices() or {}
    log_snapshot(balances, price_map, tag="before")

    # 调仓（关键！必须api=api）
    rebalance_portfolio(
        top_symbols,
        balances,
        positions,
        api.place_order,
        price_map,
        dry_run=CONFIG["DRY_RUN"],
        api=api,    # ★★★ 这里一定要传
    )

    # 资产快照后
    balances2 = api.get_balances(simulate=CONFIG["SIMULATE"])
    log_snapshot(balances2, price_map, tag="after")

    log_info("本轮交易完成\n")

if __name__ == "__main__":
    main()