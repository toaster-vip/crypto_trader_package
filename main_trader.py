# main_trader.py
import os
import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from kucoin_api import KuCoinClient
from strategy import get_symbol_score, wrap_with_timing_and_cooldown  # ✅ 新增计时器导入
from rebalancer import rebalance_portfolio
from notifier import send_serverchan_notification
from config import CONFIG, LOG_DIR

from colorama import Fore, Style, init as colorama_init
colorama_init(autoreset=True)

# ✅ 是否启用测试模式（只分析前 30 个币种）
TEST_MODE = False
# 🧵 设置最大并发线程数（推荐值：5~20）
MAX_WORKERS = 10

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.CYAN}[{timestamp}] {message}{Style.RESET_ALL}")
    with open(os.path.join(LOG_DIR, "trading.log"), "a") as f:
        f.write(f"[{timestamp}] {message}\n")

@wrap_with_timing_and_cooldown  # ✅ 外层包裹计时器 + 限速保护
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

    scores = {}

    log(f"🚀 开始并发分析 {len(usdt_symbols)} 个币种 (线程数={MAX_WORKERS})")
    with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
        future_to_symbol = {executor.submit(get_symbol_score, symbol): symbol for symbol in usdt_symbols}

        for future in as_completed(future_to_symbol):
            symbol = future_to_symbol[future]
            try:
                score = future.result()
                scores[symbol] = score
                print(f"{Fore.YELLOW}{symbol:<12} Score: {score:.3f}{Style.RESET_ALL}")
            except Exception as e:
                print(f"{Fore.RED}[ERROR] 无法分析 {symbol}: {e}{Style.RESET_ALL}")

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