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

colorama_init(autoreset=True)

TEST_MODE = False
BATCH_SIZE = 50
MAX_WORKERS = 10
BATCH_DELAY = 2
REPORT_INTERVAL = 200
POSITIONS_FILE = os.path.join(LOG_DIR, "positions.json")
COUNTER_FILE = os.path.join(LOG_DIR, "run_counter.txt")

def log(msg):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.CYAN}[{timestamp}] {msg}{Style.RESET_ALL}")
    with open(os.path.join(LOG_DIR, "trading.log"), "a") as f:
        f.write(f"[{timestamp}] {msg}\n")

def analyze_in_batches(symbols, max_workers=10, batch_size=50, delay_between_batches=2):
    scores = {}
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i + batch_size]
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(get_symbol_score, s): s for s in batch}
            for future in as_completed(futures):
                symbol = futures[future]
                try:
                    scores[symbol] = future.result()
                    print(f"{Fore.YELLOW}{symbol:<12} Score: {scores[symbol]:.3f}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}[ERROR] 分析失败 {symbol}: {e}{Style.RESET_ALL}")
        time.sleep(delay_between_batches)
    return scores

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

    scores = analyze_in_batches(symbols, max_workers=MAX_WORKERS, batch_size=BATCH_SIZE, delay_between_batches=BATCH_DELAY)
    if not scores:
        log("⚠️ 没有评分结果，跳过交易")
        return

    top = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_symbols_with_scores = top[:3]  # [(symbol, score), ...]
    log(f"🔥 评分最高币种: {[s[0] for s in top_symbols_with_scores]}")

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