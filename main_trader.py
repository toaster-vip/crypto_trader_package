# main_trader.py
import time
import os
import json
import concurrent.futures
import traceback

from config import CONFIG
from strategy import is_market_ok, get_top_gainers_and_volume, get_symbol_score
from kucoin_api import KuCoinClient, to_symbol_pair
from rebalancer import rebalance_portfolio
from log_utils import init_logger, log_snapshot, log_info, log_error

# ==== 冷却机制相关 ====
COOLDOWN_FILE = "/home/linuxuser/crypto_trader_package/cooldown_pool.json"
COOLDOWN_ROUNDS = CONFIG.get("COOLDOWN_ROUNDS", 3)  # 冷却几轮

def load_cooldown_pool():
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r") as f:
                return json.load(f)
        except Exception:
            # 文件损坏容错
            return {}
    return {}

def save_cooldown_pool(pool):
    try:
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(pool, f)
    except Exception as e:
        log_error(f"保存冷却池失败: {e}")

def active_cooldown_symbols(pool, current_round: int):
    """返回仍在冷却期内的 symbol 集合"""
    return {sym for sym, until in pool.items() if until > current_round}

def prune_cooldown_pool(pool, current_round: int) -> int:
    """移除已过期的冷却项，返回删除数量"""
    to_del = [sym for sym, until in pool.items() if until <= current_round]
    for sym in to_del:
        pool.pop(sym, None)
    return len(to_del)

def fetch_score(api, symbol):
    try:
        score_obj = get_symbol_score(api, symbol)
        return symbol, score_obj
    except Exception as e:
        log_error(f"评分失败 {symbol}: {e}")
        # 按最差处理，后续会被过滤
        return symbol, {"score": -999, "turnover": 0, "open": 0, "is_new_coin": True, "is_extreme": True}

def main():
    init_logger(CONFIG.get("LOG_LEVEL"))  # 统一日志初始化
    t0 = time.time()
    try:
        api = KuCoinClient()  # 全局只初始化一次

        # ========== 轮次编号（每4小时一轮，适配crontab）==========
        current_round = int(time.time() // (3600 * 4))
        cooldown_pool = load_cooldown_pool()
        removed = prune_cooldown_pool(cooldown_pool, current_round)
        if removed:
            log_info(f"冷却池清理完成：移除 {removed} 个已过期项")

        exclude_syms = active_cooldown_symbols(cooldown_pool, current_round)

        # ========== 市场过滤（BTC/ETH 1h MA 斜率 + 24h回撤阈值） ==========
        market_ok = is_market_ok(api)
        log_info(f"市场过滤结果 market_ok={market_ok}")

        # ========== 热点池选币 ==========
        hot_symbols = get_top_gainers_and_volume(
            api,
            top_n=CONFIG["HOT_TOP_N"],
            exclude_symbols=exclude_syms,
            market_ok=market_ok
        )

        # 统一标准化为 xxx-USDT
        hot_symbols = [to_symbol_pair(s) for s in (hot_symbols or [])]
        if not hot_symbols:
            log_error("本轮无热点币（可能因市场过滤或行情为空），本轮仅检查持仓止盈/止损，不新开仓")
            top_symbols = []
        else:
            log_info(f"本轮热点池: {hot_symbols}")

            # ========== 多线程评分 ==========
            symbol_scores = []
            with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG["DEFAULT_WORKERS"]) as executor:
                future_map = {executor.submit(fetch_score, api, s): s for s in hot_symbols}
                for fut in concurrent.futures.as_completed(future_map):
                    s = future_map[fut]
                    try:
                        sym, sc = fut.result()
                    except Exception as e:
                        log_error(f"评分线程异常 {s}: {e}")
                        continue
                    # 过滤成交额/极端波动
                    if sc.get("turnover", 0) < CONFIG["MIN_TURNOVER_1H"]:
                        continue
                    if sc.get("is_extreme", False):
                        continue
                    symbol_scores.append((sym, sc.get("score", -999), sc))

            if not symbol_scores:
                log_error("有效候选为0（成交额不足或极端波动剔除），本轮仅检查持仓止盈/止损，不新开仓")
                top_symbols = []
            else:
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

        elapsed = time.time() - t0
        log_info(f"本轮交易完成，用时 {elapsed:.2f}s\n")

    except Exception as e:
        log_error(f"main_trader 未捕获异常：{e}\n{traceback.format_exc()}")

if __name__ == "__main__":
    main()