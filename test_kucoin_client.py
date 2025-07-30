import time
from api import KuCoinClient  # 确保 api.py 中类名为 KuCoinClient

def test_kucoin_client():
    client = KuCoinClient()

    print("=== 🔍 测试 KuCoin API 功能 ===")

    # 1. 获取账户持仓
    print("\n[1] 获取账户持仓：")
    holdings = client.get_account_holdings()
    print(holdings)

    # 2. 获取交易对列表
    print("\n[2] 获取支持交易的 USDT 对：")
    symbols = client.get_supported_symbols()
    print(f"共 {len(symbols)} 个交易对，示例：", symbols[:5])

    # 3. 获取行情数据
    test_symbol = "XLM-USDT"
    print(f"\n[3] 获取行情数据：{test_symbol}")
    market_data = client.get_market_data(test_symbol)
    print(market_data)

    # 4. 获取最新价格
    print(f"\n[4] 获取当前价格：{test_symbol}")
    price = client.get_symbol_price(test_symbol)
    print(f"{test_symbol} 当前价格: {price}")

    # 5. 下市价买单（约 1 USDT）
    print(f"\n[5] 测试市价买入 {test_symbol}")
    buy_amount = 1.0
    order_id = client.place_order(test_symbol, side="buy", size=buy_amount)
    time.sleep(3)

    # 6. 下市价卖单（卖刚买入的数量，保守估 2.4 XLM）
    print(f"\n[6] 测试市价卖出 {test_symbol}")
    sell_qty = round((buy_amount / price) * 0.998, 2)
    client.place_order(test_symbol, side="sell", size=sell_qty)

    print("\n✅ 所有 API 测试完成")

if __name__ == "__main__":
    test_kucoin_client()