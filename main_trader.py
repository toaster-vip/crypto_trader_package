import time
import os
import json
import concurrent.futures
from config import CONFIG
from strategy import get_top_gainers_and_volume, get_symbol_score
from kucoin_api import KuCoinClient, to_symbol_pair
from rebalancer import rebalance_portfolio
from log_utils import log_snapshot, log_info, log_error

# ==== 冷却机制相关 ====
COOLDOWN_FILE = "/home/linuxuser/crypto_trader_package/cooldown_pool.json"
COOLDOWN_ROUNDS = CONFIG.get("COOLDOWN_ROUNDS", 3)  # 冷却3轮（比如12小时）

def load_cooldown_pool():
    if os.path.exists(COOLDOWN_FILE):
        with open(COOLDOWN_FILE, "r") as f:
            return json.load(f)
    return {}

def save_cooldown_pool(pool):
    with open(COOLDOWN_FILE, "w") as f:
        json.dump(pool, f)

def fetch_score(api, symbol):
    try:
        score_obj = get_symbol_score(api, symbol)
        return symbol, score_obj
    except Exception as e:
        log_error(f"评分失败 {symbol}: {e}")
        return symbol, {"score": -999, "turnover": 0, "open": 0, "is_new_coin": True, "is_extreme": True}

def main():
    api = KuCoinClient()  # 全局只初始化一次
    # ========== 轮次编号（每4小时一轮，适配crontab）==========
    current_round = int(time.time() // (3600 * 4))
    cooldown_pool = load_cooldown_pool()

    # ========== 热点池选币 ==========
    hot_symbols = get_top_gainers_and_volume(api, top_n=CONFIG["HOT_TOP_N"])
    if not hot_symbols:
        log_error("本轮无热点币，暂停运行")
        return
    hot_symbols = [to_symbol_pair(s) for s in hot_symbols]
    log_info(f"本轮热点池: {hot_symbols}")

    # ========== 多线程评分 ==========
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG["DEFAULT_WORKERS"]) as executor:
        futures = [executor.submit(fetch_score, api, s) for s in hot_symbols]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]

    # ========== 过滤和TopN ==========
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

    # ========== 资产快照前 ==========
    balances = api.get_balances(simulate=CONFIG["SIMULATE"])
    positions = api.get_positions(simulate=CONFIG["SIMULATE"])
    price_map = api.get_all_prices() or {}
    log_snapshot(balances, price_map, tag="before")

    # ========== 调仓 ==========
    rebalance_portfolio(
        top_symbols,
        balances,
        positions,
        api.place_order,
        price_map,
        dry_run=CONFIG["DRY_RUN"],
        api=api,
        cooldown_pool=cooldown_pool,        # 传入冷却池
        current_round=current_round,        # 传入当前轮
        cooldown_rounds=COOLDOWN_ROUNDS     # 传入冷却几轮
    )

    # ========== 保存最新冷却池 ==========
    save_cooldown_pool(cooldown_pool)

    # ========== 资产快照后 ==========
    balances2 = api.get_balances(simulate=CONFIG["SIMULATE"])
    log_snapshot(balances2, price_map, tag="after")

    log_info("本轮交易完成\n")

if __name__ == "__main__":
    main()