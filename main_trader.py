# main_trader.py
import os
import sys
import logging
import datetime
from config import LOG_DIR
from api import client
from analyzer import analyze_all_symbols
from rebalancer import rebalance_portfolio

# ✅ 设置日志
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

today = datetime.datetime.now().strftime("%Y-%m-%d")
log_path = os.path.join(LOG_DIR, f"trade_{today}.log")

logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='[%(asctime)s] %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def log(msg):
    print(msg)
    logging.info(msg)

def run():
    log("✅ 自动交易系统启动中...")

    # 1. 获取推荐币种（按评分排序）
    try:
        from config import CONFIG

        # 获取配置中 SYMBOLS 或从 client 动态拉取
        symbols_to_analyze = CONFIG.get("SYMBOLS", [])
        if not symbols_to_analyze:
        try:
            symbols_to_analyze = client.get_valid_symbols()
        except Exception as e:
            log(f"[WARN] 获取支持币种失败：{e}")
            symbols_to_analyze = []

# 调用分析函数
recommended = analyze_all_symbols(client, symbols_to_analyze)
        recommended = analyze_all_symbols()
    except Exception as e:
        log(f"[ERROR] 分析失败: {e}")
        return

    if not recommended:
        log("⚠️ 没有发现任何潜力币种，跳过本轮。")
        return

    # 2. 执行调仓逻辑
    try:
        top_symbols = [item["symbol"] for item in recommended]
        log(f"📊 本轮推荐币种：{top_symbols}")
        rebalance_portfolio(top_symbols)
    except Exception as e:
        log(f"[ERROR] 调仓失败: {e}")
        return

    log("✅ 本轮交易完成。")

if __name__ == "__main__":
    try:
        run()
    except Exception as e:
        logging.exception(f"系统运行异常: {e}")
        print(f"\033[91m[致命错误] 系统崩溃: {e}\033[0m")
        sys.exit(1)