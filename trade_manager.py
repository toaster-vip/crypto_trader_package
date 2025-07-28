from datetime import datetime
from config import IS_REAL_TRADING, TAKE_PROFIT, STOP_LOSS
from notifier import send_wechat_notification

# 用于模拟交易记录（如使用真实交易，可改为实际订单系统）
portfolio = {}

def execute_trade(symbol, signal, data):
    price = float(data["price"]) if "price" in data else None
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if symbol not in portfolio:
        portfolio[symbol] = {
            "holding": False,
            "buy_price": 0.0,
            "buy_time": "",
        }

    position = portfolio[symbol]

    # 买入信号
    if signal > 0.2 and not position["holding"]:
        print(f"[BUY] 买入 {symbol} @ {price} at {timestamp}")
        position["holding"] = True
        position["buy_price"] = price
        position["buy_time"] = timestamp

        if IS_REAL_TRADING:
            # 真实下单逻辑放这里（调用交易所 API）
            pass

        send_wechat_notification(
            f"💰 成交：买入 {symbol}",
            f"价格：{price}\n时间：{timestamp}"
        )

    # 卖出信号
    elif signal < -0.2 and position["holding"]:
        print(f"[SELL] 卖出 {symbol} @ {price} at {timestamp}")
        position["holding"] = False
        pnl = round((price - position["buy_price"]) / position["buy_price"] * 100, 2)

        if IS_REAL_TRADING:
            # 真实卖出逻辑放这里
            pass

        send_wechat_notification(
            f"💸 成交：卖出 {symbol}",
            f"价格：{price}\n盈亏：{pnl}%\n时间：{timestamp}"
        )

    # 止盈止损判断（在持仓状态下）
    elif position["holding"]:
        entry = position["buy_price"]
        change = (price - entry) / entry
        if change >= TAKE_PROFIT:
            print(f"[TP] 止盈 {symbol} @ {price} (+{change*100:.2f}%)")
            position["holding"] = False
            send_wechat_notification(
                f"✅ 止盈卖出 {symbol}",
                f"价格：{price}\n盈利：{change*100:.2f}%\n时间：{timestamp}"
            )
        elif change <= -STOP_LOSS:
            print(f"[SL] 止损 {symbol} @ {price} ({change*100:.2f}%)")
            position["holding"] = False
            send_wechat_notification(
                f"⚠️ 止损卖出 {symbol}",
                f"价格：{price}\n亏损：{change*100:.2f}%\n时间：{timestamp}"
            )
    else:
        print(f"[HOLD] 继续观望 {symbol}")