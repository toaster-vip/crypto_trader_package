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
from notifier import send_serverchan_notification

# ==== 冷却机制相关 ====
COOLDOWN_FILE = "/home/linuxuser/crypto_trader_package/cooldown_pool.json"
COOLDOWN_ROUNDS = CONFIG.get("COOLDOWN_ROUNDS", 3)

def load_cooldown_pool():
    if os.path.exists(COOLDOWN_FILE):
        try:
            with open(COOLDOWN_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_cooldown_pool(pool):
    try:
        with open(COOLDOWN_FILE, "w") as f:
            json.dump(pool, f)
    except Exception as e:
        log_error(f"保存冷却池失败: {e}")

def active_cooldown_symbols(pool, current_round: int):
    return {sym for sym, until in pool.items() if until > current_round}

def prune_cooldown_pool(pool, current_round: int) -> int:
    to_del = [sym for sym, until in pool.items() if until <= current_round]
    for sym in to_del:
        pool.pop(sym, None)
    return len(to_del)

def _portfolio_value(positions: dict, price_map: dict) -> float:
    total = 0.0
    for sym, pos in (positions or {}).items():
        sym2 = to_symbol_pair(sym)
        amt = float(pos.get("amount", 0) if isinstance(pos, dict) else 0)
        px = float(price_map.get(sym2, 0) or 0)
        total += amt * px
    return total

def _fmt_pct(x):
    try:
        return f"{x*100:.2f}%"
    except Exception:
        return "NA"

def build_run_summary_md(
    start_ts: float,
    market_ok: bool,
    hot_symbols: list,
    top_symbols: list,
    balances_before: dict,
    balances_after: dict,
    prices_before: dict,
    prices_after: dict,
    summary: dict,
    current_round: int,
    elapsed_s: float
):
    from datetime import datetime
    ts_str = datetime.fromtimestamp(start_ts).strftime("%Y-%m-%d %H:%M:%S")
    title = f"[交易轮次完成] {ts_str} (round={current_round})"

    usdt_b = float(balances_before.get("USDT", 0) or 0)
    usdt_a = float(balances_after.get("USDT", 0) or 0)

    sells = summary.get("sells", []) if summary else []
    buys = summary.get("buys", []) if summary else []
    notes = summary.get("notes", []) if summary else []
    cd_updates = summary.get("cooldown_updates", []) if summary else []

    overview = []
    overview.append(f"- 市场过滤：{'✅' if market_ok else '❌'}")
    overview.append(f"- 候选/TopN：{len(hot_symbols or [])} / {len(top_symbols or [])}")
    overview.append(f"- 卖出：{len(sells)} 笔；买入：{len(buys)} 笔")
    overview.append(f"- USDT：{usdt_b:.2f} → {usdt_a:.2f}")
    overview.append(f"- 用时：{elapsed_s:.2f}s")

    sell_lines = [
        "| symbol | amount | entry | price | PnL% | reason | cooldown |",
        "|---|---:|---:|---:|---:|---|---:|",
    ]
    for s in sells:
        sell_lines.append(
            f"| {s.get('symbol','')} | {s.get('amount',0):.6g} | {s.get('entry',0):.6g} | "
            f"{s.get('price',0):.6g} | {_fmt_pct(s.get('pnl_pct',0))} | {s.get('reason','')} | "
            f"{s.get('cooldown_until','')} |"
        )
    sells_md = "\n".join(sell_lines) if sells else "_无_"

    buy_lines = ["| symbol | funds(USDT) | price | orderid |", "|---|---:|---:|---|"]
    for b in buys:
        pr = b.get("price")
        pr_str = "NA" if pr in (None, "NA") else f"{float(pr):.6g}"
        buy_lines.append(
            f"| {b.get('symbol','')} | {float(b.get('funds',0)):.6g} | {pr_str} | {b.get('orderid','')} |"
        )
    buys_md = "\n".join(buy_lines) if buys else "_无_"

    cd_md = ", ".join([f"{c.get('symbol','')}→{c.get('until','')}" for c in cd_updates]) if cd_updates else "_无_"
    notes_md = ("; ".join(notes)) if notes else "_无_"
    hot_md = ", ".join((hot_symbols or [])[:10]) + (" ..." if hot_symbols and len(hot_symbols) > 10 else "")
    top_md = ", ".join(top_symbols or [])

    md = []
    md.append("## 概览")
    md.extend(overview)
    md.append("\n## 候选与TopN")
    md.append(f"- 候选（最多10项）: {hot_md if hot_md else '_无_'}")
    md.append(f"- TopN: {top_md if top_md else '_无_'}")
    md.append("\n## 卖出")
    md.append(sells_md)
    md.append("\n## 买入")
    md.append(buys_md)
    md.append("\n## 冷却池更新")
    md.append(cd_md)
    md.append("\n## 告警/异常")
    md.append(notes_md)

    content = "\n".join(md)
    return title, content

def fetch_score(api, symbol):
    try:
        score_obj = get_symbol_score(api, symbol)
        return symbol, score_obj
    except Exception as e:
        log_error(f"评分失败 {symbol}: {e}")
        return symbol, {"score": -999, "turnover": 0, "open": 0, "is_new_coin": True, "is_extreme": True}

def main():
    init_logger(CONFIG.get("LOG_LEVEL"))
    start_ts = time.time()
    balances_before = {}
    balances_after = {}
    prices_before = {}
    prices_after = {}
    hot_symbols = []
    top_symbols = []
    summary = {}

    try:
        api = KuCoinClient()
        current_round = int(time.time() // (3600 * 4))

        # 冷却池读取与清理
        cooldown_pool = load_cooldown_pool()
        removed = prune_cooldown_pool(cooldown_pool, current_round)
        if removed:
            log_info(f"冷却池清理完成：移除 {removed} 个已过期项")
        exclude_syms = active_cooldown_symbols(cooldown_pool, current_round)

        # 市场过滤
        market_ok = is_market_ok(api)
        log_info(f"市场过滤结果 market_ok={market_ok}")

        # 候选池（strategy 内部已包含 4h 硬过滤 + 动态放宽）
        hot_symbols = get_top_gainers_and_volume(
            api,
            top_n=CONFIG["HOT_TOP_N"],
            exclude_symbols=exclude_syms,
            market_ok=market_ok
        ) or []
        hot_symbols = [to_symbol_pair(s) for s in hot_symbols]
        if hot_symbols:
            log_info(f"本轮热点池: {hot_symbols}")
        else:
            log_error("本轮无热点币（可能因市场过滤或行情为空），本轮仅检查持仓止盈/止损，不新开仓")

        # 打分选 TopN
        if hot_symbols:
            log_info(f"当前成交额门槛 MIN_TURNOVER_1H={CONFIG.get('MIN_TURNOVER_1H')}")
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
                top_symbols = [x[0] for x in symbol_scores[:CONFIG["TOP_N"]]]
                log_info(f"本轮选中TopN: {top_symbols}")
        else:
            top_symbols = []

        # 快照（前）
        balances_before = api.get_balances(simulate=CONFIG["SIMULATE"])
        positions_before = api.get_positions(simulate=CONFIG["SIMULATE"])
        prices_before = api.get_all_prices() or {}
        log_snapshot(balances_before, prices_before, tag="before")

        # 调仓
        summary = rebalance_portfolio(
            top_symbols,
            balances_before,
            positions_before,
            api.place_order,
            prices_before,
            dry_run=CONFIG["DRY_RUN"],
            api=api,
            cooldown_pool=cooldown_pool,
            current_round=current_round,
            cooldown_rounds=COOLDOWN_ROUNDS
        ) or {}

        # 冷却池保存
        save_cooldown_pool(cooldown_pool)

        # 快照（后）
        balances_after = api.get_balances(simulate=CONFIG["SIMULATE"])
        prices_after = api.get_all_prices() or {}
        log_snapshot(balances_after, prices_after, tag="after")

        # 通知
        elapsed = time.time() - start_ts
        title, content = build_run_summary_md(
            start_ts=start_ts,
            market_ok=market_ok,
            hot_symbols=hot_symbols,
            top_symbols=top_symbols,
            balances_before=balances_before,
            balances_after=balances_after,
            prices_before=prices_before,
            prices_after=prices_after,
            summary=summary,
            current_round=current_round,
            elapsed_s=elapsed
        )
        try:
            send_serverchan_notification(title, content)
        except Exception as ne:
            log_error(f"Server酱通知发送失败：{ne}")

        log_info(f"本轮交易完成，用时 {elapsed:.2f}s\n")

    except Exception as e:
        log_error(f"main_trader 未捕获异常：{e}\n{traceback.format_exc()}")
        try:
            elapsed = time.time() - start_ts
            title = "[告警] main_trader 异常退出"
            content = f"错误：{e}\n\n{traceback.format_exc()}\n\n用时：{elapsed:.2f}s"
            send_serverchan_notification(title, content)
        except Exception:
            pass
    finally:
        try:
            if "cooldown_pool" in locals():
                save_cooldown_pool(cooldown_pool)
        except Exception:
            pass

if __name__ == "__main__":
    main()