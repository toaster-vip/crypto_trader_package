from config import SUPPORTED_SYMBOLS, IS_REAL_TRADING
from api import get_account_holdings, get_market_data
import time
from datetime import datetime
from config import (
    IS_REAL_TRADING, SUPPORTED_SYMBOLS, TAKE_PROFIT, STOP_LOSS,
    STRATEGY_WEIGHTS, THRESHOLDS
)
from api import get_market_data, get_all_symbols, get_account_holdings
from strategy import calculate_signal
from notifier import send_wechat_notification

portfolio = {}

def execute_trade(symbol, signal, data):
    price = float(data.get("price"))
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if symbol not in portfolio:
        portfolio[symbol] = {
            "holding": False,
            "buy_price": 0.0,
            "buy_time": "",
        }

    position = portfolio[symbol]

    # 买入逻辑
    if signal > THRESHOLDS["buy"] and not position["holding"]:
        print(f"\033[92m[BUY] 买入 {symbol} @ {price} at {timestamp}\033[0m")
        position["holding"] = True
        position["buy_price"] = price
        position["buy_time"] = timestamp

        if IS_REAL_TRADING:
            # 实际下单逻辑
            pass

        send_wechat_notification(
            f"💰 成交：买入 {symbol}",
            f"价格：{price}\n时间：{timestamp}"
        )

    # 卖出逻辑
    elif signal < THRESHOLDS["sell"] and position["holding"]:
        print(f"\033[91m[SELL] 卖出 {symbol} @ {price} at {timestamp}\033[0m")
        position["holding"] = False
        pnl = round((price - position["buy_price"]) / position["buy_price"] * 100, 2)

        if IS_REAL_TRADING:
            # 实际卖出逻辑
            pass

        send_wechat_notification(
            f"💸 成交：卖出 {symbol}",
            f"价格：{price}\n盈亏：{pnl}%\n时间：{timestamp}"
        )

    # 止盈止损逻辑
    elif position["holding"]:
        change = (price - position["buy_price"]) / position["buy_price"]
        if change >= TAKE_PROFIT:
            print(f"\033[94m[TP] 止盈 {symbol} @ {price} (+{change*100:.2f}%)\033[0m")
            position["holding"] = False
            send_wechat_notification(
                f"✅ 止盈卖出 {symbol}",
                f"价格：{price}\n盈利：{change*100:.2f}%\n时间：{timestamp}"
            )
        elif change <= -STOP_LOSS:
            print(f"\033[91m[SL] 止损 {symbol} @ {price} ({change*100:.2f}%)\033[0m")
            position["holding"] = False
            send_wechat_notification(
                f"⚠️ 止损卖出 {symbol}",
                f"价格：{price}\n亏损：{change*100:.2f}%\n时间：{timestamp}"
            )
    else:
        print(f"\033[90m[HOLD] 继续观望 {symbol}\033[0m")

def main():
    print("✅ 自动交易脚本已启动")
    raw_holdings = get_account_holdings()
    holdings = filter_valid_holdings(raw_holdings)
    market_symbols = get_all_symbols()

    if not market_symbols:
        print("❌ 获取币种失败")
        send_wechat_notification("❌ 自动交易异常 - 获取币种失败", "")
        return

    print(f"🎯 本轮检测币种：{market_symbols}")
    for symbol in market_symbols:
        try:
            print(f"\n🔍 处理 {symbol} 中...")
            data = get_market_data(symbol)
            signal = calculate_signal(symbol, data)
            print(f"📈 策略信号为：{signal}")
            in_hold = symbol in holdings

            if in_hold and signal < THRESHOLDS["sell"]:
                execute_trade(symbol, signal, data)
            elif not in_hold and signal > THRESHOLDS["buy"]:
                execute_trade(symbol, signal, data)
            else:
                print(f"\033[90m[SKIP] 无需操作 {symbol}\033[0m")
        except Exception as e:
            print(f"❌ {symbol} 出错：{e}")
            send_wechat_notification(f"❌ 自动交易异常 - {symbol}", str(e))

    print("\n✅ 所有币种处理完成，脚本结束。\n")

if __name__ == "__main__":
    main()