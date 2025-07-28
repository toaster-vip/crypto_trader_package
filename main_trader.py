import time
from datetime import datetime
from api import get_account_holdings, get_market_data, filter_valid_holdings
from strategy import calculate_signal
from config import IS_REAL_TRADING, TAKE_PROFIT, STOP_LOSS, STRATEGY_WEIGHTS, THRESHOLDS
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

    if signal > THRESHOLDS["buy"] and not position["holding"]:
        print(f"\033[92m[BUY] 买入 {symbol} @ {price} at {timestamp}\033[0m")
        position.update({"holding": True, "buy_price": price, "buy_time": timestamp})

        if IS_REAL_TRADING:
            pass  # 实际下单逻辑

        send_wechat_notification(f"💰 成交：买入 {symbol}", f"价格：{price}\n时间：{timestamp}")

    elif signal < THRESHOLDS["sell"] and position["holding"]:
        print(f"\033[91m[SELL] 卖出 {symbol} @ {price} at {timestamp}\033[0m")
        pnl = round((price - position["buy_price"]) / position["buy_price"] * 100, 2)
        position["holding"] = False

        if IS_REAL_TRADING:
            pass  # 实际卖出逻辑

        send_wechat_notification(f"💸 成交：卖出 {symbol}", f"价格：{price}\n盈亏：{pnl}%\n时间：{timestamp}")

    elif position["holding"]:
        change = (price - position["buy_price"]) / position["buy_price"]
        if change >= TAKE_PROFIT:
            print(f"\033[94m[TP] 止盈 {symbol} @ {price} (+{change*100:.2f}%)\033[0m")
            position["holding"] = False
            send_wechat_notification(f"✅ 止盈卖出 {symbol}", f"价格：{price}\n盈利：{change*100:.2f}%\n时间：{timestamp}")
        elif change <= -STOP_LOSS:
            print(f"\033[91m[SL] 止损 {symbol} @ {price} ({change*100:.2f}%)\033[0m")
            position["holding"] = False
            send_wechat_notification(f"⚠️ 止损卖出 {symbol}", f"价格：{price}\n亏损：{change*100:.2f}%\n时间：{timestamp}")
    else:
        print(f"\033[90m[HOLD] 继续观望 {symbol}\033[0m")

def main():
    print(f"\n[INFO] ✅ 自动交易脚本已启动")
    try:
        raw_holdings = get_account_holdings()
        holdings = filter_valid_holdings(raw_holdings)
    except Exception as e:
        print(f"❌ 获取持仓信息失败：{e}")
        send_wechat_notification("❌ 自动交易异常 - 持仓获取失败", str(e))
        return

    if not holdings:
        print("⚠️ 未检测到支持交易的有效持仓币种")
        return

    print(f"\n🎯 本轮检测币种：{[h['symbol'] for h in holdings]}")
    for h in holdings:
        symbol = h["symbol"]
        try:
            print(f"\n🔍 处理 {symbol} 中...")
            data = get_market_data(symbol)
            signal = calculate_signal(symbol, data)
            print(f"📈 策略信号为：{signal:.2f}")
            execute_trade(symbol, signal, data)
        except Exception as e:
            print(f"❌ {symbol} 出错：{e}")
            send_wechat_notification(f"❌ 自动交易异常 - {symbol}", str(e))

    print("\n✅ 所有币种处理完成，脚本结束。\n")

if __name__ == "__main__":
    main()