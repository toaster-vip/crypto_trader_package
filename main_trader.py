# main_trader.py
import os
import datetime
from kucoin_api import KuCoinClient
from strategy import get_symbol_score
from rebalancer import rebalance_portfolio
from notifier import send_serverchan_notification
from config import CONFIG, LOG_DIR

from colorama import Fore, Style, init as colorama_init
colorama_init(autoreset=True)

# ✅ 是否启用测试模式（只分析前 30 个币种）
TEST_MODE = True

def log(message):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"{Fore.CYAN}[{timestamp}] {message}{Style.RESET_ALL}")
    with open(os.path.join(LOG_DIR, "trading.log"), "a") as f:
        f.write(f"[{timestamp}] {message}\n")

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
    for symbol in usdt_symbols:
        try:
            score = get_symbol_score(symbol)
            scores[symbol] = score
            print(f"{Fore.YELLOW}{symbol:<12} Score: {score:.3f}{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.RED}[ERROR] 无法分析 {symbol}: {e}{Style.RESET_ALL}")

    if not scores:
        log("⚠️ 没有可用的评分结果，跳过交易。")
        return

    # 排序并选出潜力币种
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    top_symbols = [s[0] for s in sorted_scores[:3]]
    log(f"🔥 评分最高币种: {top_symbols}")

    rebalance_portfolio(client, holdings, top_symbols)

    log("✅ 本轮交易执行完毕")

if __name__ == "__main__":
    main()