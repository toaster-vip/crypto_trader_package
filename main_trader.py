# main_trader.py
import time
import concurrent.futures
from config import CONFIG
from kucoin_api import KuCoinClient, to_symbol_pair
from strategy import get_top_gainers_and_volume, get_symbol_score
from rebalancer import rebalance_portfolio
from log_utils import log_snapshot, log_info, log_error
import os
import json

COOLDOWN_FILE = "/home/linuxuser/crypto_trader_package/cooldown_pool.json"
COOLDOWN_ROUNDS = CONFIG.get("COOLDOWN_ROUNDS", 3)


class TraderEngine:
    def __init__(self):
        self.api = KuCoinClient()
        self.cooldown_file = COOLDOWN_FILE
        self.cooldown_rounds = COOLDOWN_ROUNDS
        self.cooldown_pool = self._load_cooldown_pool()
        self.current_round = int(time.time() // (3600 * 4))

    def _load_cooldown_pool(self):
        if os.path.exists(self.cooldown_file):
            with open(self.cooldown_file, "r") as f:
                return json.load(f)
        return {}

    def _save_cooldown_pool(self):
        with open(self.cooldown_file, "w") as f:
            json.dump(self.cooldown_pool, f)

    def _fetch_score(self, symbol):
        try:
            score_obj = get_symbol_score(self.api, symbol)
            return symbol, score_obj
        except Exception as e:
            log_error(f"[评分失败] {symbol}: {e}")
            return symbol, {
                "score": -999,
                "turnover": 0,
                "open": 0,
                "is_new_coin": True,
                "is_extreme": True
            }

    def run(self):
        # 1. 获取热点币池
        hot_symbols = get_top_gainers_and_volume(self.api, top_n=CONFIG["HOT_TOP_N"])
        if not hot_symbols:
            log_error("[终止] 本轮无热点币，暂停运行。")
            return

        hot_symbols = [to_symbol_pair(s) for s in hot_symbols]
        log_info(f"[候选池] 本轮热点前{CONFIG['HOT_TOP_N']}币种: {hot_symbols}")

        # 2. 多线程评分
        symbol_scores = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=CONFIG["DEFAULT_WORKERS"]) as executor:
            futures = [executor.submit(self._fetch_score, s) for s in hot_symbols]
            for future in concurrent.futures.as_completed(futures):
                s, sc = future.result()
                if sc["turnover"] < CONFIG["MIN_TURNOVER_1H"]:
                    continue
                if sc["is_extreme"]:
                    continue
                symbol_scores.append((s, sc["score"], sc))

        if not symbol_scores:
            log_info("[终止] 所有候选币均被过滤（成交额不足或波动过大）。")
            return

        symbol_scores.sort(key=lambda x: x[1], reverse=True)
        top_n = CONFIG["TOP_N"]
        top_symbols = [x[0] for x in symbol_scores[:top_n]]
        log_info(f"[最终入选] Top{top_n}: {top_symbols}")

        # 3. 调仓前资产快照
        balances = self.api.get_balances(simulate=CONFIG["SIMULATE"])
        positions = self.api.get_positions(simulate=CONFIG["SIMULATE"])
        price_map = self.api.get_all_prices()
        log_snapshot(balances, price_map, tag="before")

        # 4. 调仓核心流程
        rebalance_portfolio(
            top_symbols=top_symbols,
            balances=balances,
            positions=positions,
            place_order=self.api.place_order,
            price_map=price_map,
            dry_run=CONFIG["DRY_RUN"],
            api=self.api,
            cooldown_pool=self.cooldown_pool,
            current_round=self.current_round,
            cooldown_rounds=self.cooldown_rounds
        )

        # 5. 调仓后资产快照 + 保存冷却池
        balances_after = self.api.get_balances(simulate=CONFIG["SIMULATE"])
        log_snapshot(balances_after, price_map, tag="after")
        self._save_cooldown_pool()

        log_info("✅ 本轮交易流程已完成。\n")


if __name__ == "__main__":
    TraderEngine().run()