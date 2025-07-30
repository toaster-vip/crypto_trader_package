# main_trader.py

import os
import time
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from kucoin_api import KuCoinClient
from strategy import get_symbol_score
from rebalancer import rebalance_portfolio
from notifier import send_serverchan_notification
from config import CONFIG, LOG_DIR

from colorama import Fore, Style, init as colorama_init
colorama_init(autoreset=True)

# ✅ 是否启用测试模式（只分析前 30 个币种）
TEST_MODE = False

# ✅ 每批处理数量
BATCH_SIZE = 50

# ✅ 最大并发线程数
MAX_WORKERS = 10

# ✅ 每批之间的延迟秒数
BATCH_DELAY = 2


def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.CYAN}[{timestamp}] {message}{Style.RESET_ALL}")
    with open(os.path.join(LOG_DIR, "trading.log"), "a") as f:
        f.write(f"[{timestamp}] {message}\n")


def analyze_in_batches(symbols, max_workers=10, batch_size=50, delay_between_batches=2):
    scores = {}
    total = len(symbols)
    batch_count = (total + batch_size - 1) // batch_size
    log(f"🚀 共需分析 {total} 个币种，将分为 {batch_count} 批，每批 {batch_size} 个，线程数={max_workers}")

    start_time = time.time()

    for i in range(0, total, batch_size):
        batch = symbols[i:i + batch_size]
        log(f"📦 开始分析第 {i // batch_size + 1}/{batch_count} 批，共 {len(batch)} 个币种")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_symbol = {executor.submit(get_symbol_score, symbol): symbol for symbol in batch}

            for future in as_completed(future_to_symbol):
                symbol = future_to_symbol[future]
                try:
                    score = future.result()
                    scores[symbol] = score
                    print(f"{Fore.YELLOW}{symbol:<12} Score: {score:.3f}{Style.RESET_ALL}")
                except Exception as e:
                    print(f"{Fore.RED}[ERROR] 无法分析 {symbol}: {e}{Style.RESET_ALL}")

        log(f"🌙 冷却中：等待 {delay_between_batches} 秒避免触发 KuCoin 限速...")
        time.sleep(delay_between_batches)

    elapsed = round(time.time() - start_time, 2)
    log(f"✅ 本轮评分完成，用时：{elapsed} 秒")
    return scores


def main():
    log("📈 自动交易脚本开始执行")
    client = KuCoinClient()

    holdings = client.get_account_holdings()
    log(f"✅ 当前持仓币种: {list(holdings.keys())}")

    supported_symbols = client.get_supported_symbols()
    usdt_symbols = [s for s in supported_symbols if s.endswith("USDT")]

    if TEST_MODE:
        log("🧪 [TEST MODE] 只分析前 30 个 USDT 币种")
        usdt_symbols = usdt_symbols[:30]

    # 分批执行并发评分
    scores = analyze_in_batches(usdt_symbols, max_workers=MAX_WORKERS, batch_size=BATCH_SIZE, delay_between_batches=BATCH_DELAY)

    if not scores:
        log("⚠️ 没有可用的评分结果，跳过交易。")
        return

    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_symbols = [s[0] for s in sorted_scores[:3]]
    log(f"🔥 评分最高币种: {top_symbols}")

    rebalance_portfolio(client, holdings, top_symbols)

    log("✅ 本轮交易执行完毕")


if __name__ == "__main__":
    main()