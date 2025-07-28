import traceback
from config import SUPPORTED_SYMBOLS
from strategy import calculate_signal
from trade_manager import execute_trade
from api import get_market_data
from notifier import send_wechat_notification

def main():
    print("\033[96m✅ 自动交易脚本已启动\033[0m")
    symbols = SUPPORTED_SYMBOLS
    print(f"🎯 本轮检测币种：{symbols}")

    for symbol in symbols:
        print(f"\n🔍 处理 {symbol} 中...")

        try:
            data = get_market_data(symbol)
            if not data:
                print(f"\033[93m[警告] 无法获取 {symbol} 行情数据，跳过。\033[0m")
                continue

            signal = calculate_signal(symbol, data)
            print(f"📈 策略信号为：{signal}")
            execute_trade(symbol, signal, data)

        except Exception as e:
            err_msg = f"{symbol} 出错：{str(e)}\n{traceback.format_exc()}"
            print(f"\033[91m❌ {err_msg}\033[0m")
            send_wechat_notification(f"❌ 自动交易异常 - {symbol}", err_msg)

    print("\n\033[92m✅ 所有币种处理完成，脚本结束。\033[0m")

if __name__ == "__main__":
    main()