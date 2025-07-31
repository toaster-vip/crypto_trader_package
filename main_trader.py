# main_trader.py

import os
import time
import json
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from kucoin_api import KuCoinClient
from strategy import get_symbol_score
from rebalancer import rebalance_portfolio
from notifier import send_serverchan_notification
from config import CONFIG, LOG_DIR
from colorama import Fore, Style, init as colorama_init
from dotenv import load_dotenv
load_dotenv()

print("🧩 [main_trader.py] 加载 config.py 成功")
print("🔑 当前配置中的 API_KEY:", CONFIG["KUCOIN_API_KEY"])

colorama_init(autoreset=True)

# ✅ 从 config 中读取运行参数
RUN_MODE = CONFIG["RUN_MODE"]
TEST_MODE = RUN_MODE["TEST_MODE"]
BATCH_SIZE = RUN_MODE["BATCH_SIZE"]
MAX_WORKERS = RUN_MODE["MAX_WORKERS"]
BATCH_DELAY = RUN_MODE["BATCH_DELAY"]
REPORT_INTERVAL = RUN_MODE["REPORT_INTERVAL"]

POSITIONS_FILE = os.path.join(LOG_DIR, "positions.json")
COUNTER_FILE = os.path.join(LOG_DIR, "run_counter.txt")

def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.CYAN}[{timestamp}] {msg}{Style.RESET_ALL}")
    with open(os.path.join(LOG_DIR, "trading.log"), "a") as f:
        f.write(f"[{timestamp}] {msg}\n")

def analyze_in_batches(symbols, max_workers=10, batch_size=50, delay_between_batches=2):
    results = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(get_symbol_score, s): s for s in batch}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    result = future.result()
                    results[symbol] = result
                    print(f"{Fore.YELLOW}{symbol:<12} Score: {result['score']:.3f} Vol: {result['volume']:.2f}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}[ERROR] 分析失败 {symbol}: {e}{Style.RESET_ALL}")
        time.sleep(delay_between_batches)
    return results

def load_json(path):
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}

def save_json(data, path):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)

def update_run_counter():
    counter = 0
    if os.path.exists(COUNTER_FILE):
        with open(COUNTER_FILE, "r") as f:
            counter = int(f.read().strip())
    counter += 1
    with open(COUNTER_FILE, "w") as f:
        f.write(str(counter))
    return counter

def generate_profit_report(client):
    positions = load_json(POSITIONS_FILE)
    holdings = client.get_account_holdings()
    total_cost = 0
    total_value = 0
    lines = []

    for symbol, info in positions.items():
        if symbol not in holdings or float(holdings[symbol]) <= 0:
            continue
        entry_price = info["entry_price"]
        qty = float(holdings[symbol])
        current_price = client.get_symbol_price(f"{symbol}-USDT")
        value = qty * current_price
        cost = qty * entry_price
        pnl = (value - cost) / cost * 100
        total_cost += cost
        total_value += value
        lines.append(f"{symbol}: 入场 {entry_price:.4f}，现价 {current_price:.4f}，数量 {qty:.2f}，盈亏 {pnl:.2f}%")

    summary = f"\n💰 当前总市值：{total_value:.2f} USDT\n💸 成本合计：{total_cost:.2f} USDT\n📊 盈亏：{(total_value - total_cost):.2f} USDT ({((total_value - total_cost)/total_cost*100 if total_cost else 0):.2f}%)"
    content = "\n".join(lines) + summary if lines else "当前无持仓，空仓中。"
    send_serverchan_notification("📊 每日盈亏报告", content)

def main():
    start_time = time.time()
    log("📈 自动交易脚本开始执行")
    client = KuCoinClient()
    holdings = client.get_account_holdings()
    log(f"✅ 当前持仓币种: {list(holdings.keys())}")

    symbols = [s for s in client.get_supported_symbols() if s.endswith("USDT")]
    if TEST_MODE:
        symbols = symbols[:30]

    results = analyze_in_batches(
        symbols,
        max_workers=MAX_WORKERS,
        batch_size=BATCH_SIZE,
        delay_between_batches=BATCH_DELAY
    )

    if not results:
        log("⚠️ 没有评分结果，跳过交易")
        return

    # 拆分为分数和成交量
    scores = {s: v["score"] for s, v in results.items()}
    volumes = {s: v["volume"] for s, v in results.items()}

    log("📊 开始排序 top N 币种评分（含成交量辅助）...")
    top = sorted(scores.items(), key=lambda x: (x[1], volumes.get(x[0], 0)), reverse=True)
    top_symbols_with_scores = top[:3]
    print("✅ 排序完成，前3名为：", top_symbols_with_scores)

    log(f"🔥 评分最高币种: {[s[0] for s in top_symbols_with_scores]}")
    log("🧠 调仓逻辑开始执行 rebalance_portfolio()")
    rebalance_portfolio(client, holdings, top_symbols_with_scores, POSITIONS_FILE)
    log("✅ 本轮交易执行完毕")

    count = update_run_counter()
    if count % REPORT_INTERVAL == 0:
        log("📬 生成定期盈亏报告")
        generate_profit_report(client)

    elapsed = time.time() - start_time
    log(f"⏱️ 本轮运行耗时: {elapsed:.2f} 秒")

if __name__ == "__main__":
    main()