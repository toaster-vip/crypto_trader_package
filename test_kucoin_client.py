import time
from kucoin_api import KuCoinClient

def test_kucoin_client():
    client = KuCoinClient()

    print("=== 🔍 测试 KuCoin API 功能 ===")

    # 1. 获取账户持仓
    print("\n[1] 获取账户持仓：")
    holdings = client.get_account_holdings()
    print(holdings)

    # 1.1 获取主账户 USDT 可用余额
    print("\n[1.1] 获取主账户中 USDT 可用余额：")
    usdt_balance = holdings.get("USDT", 0.0)
    print(f"当前 USDT 余额：{usdt_balance} USDT")

    # 2. 获取支持的 USDT 交易对
    print("\n[2] 获取支持交易的 USDT 对：")
    symbols = client.get_supported_symbols()
    print(f"共 {len(symbols)} 个交易对，示例：", symbols[:5])

    # 3. 获取行情数据
    test_symbol = "XLM-USDT"
    print(f"\n[3] 获取行情数据：{test_symbol}")
    market_data = client.get_market_data(test_symbol)
    print(market_data)

    # 4. 获取实时价格
    print(f"\n[4] 获取当前价格：{test_symbol}")
    price = client.get_symbol_price(test_symbol)
    print(f"{test_symbol} 当前价格: {price}")

    # 5. 获取成交明细（fills，真实买入/卖出）
    print(f"\n[5] 获取历史成交明细 fills（测试币种：{test_symbol}，只取最新5条买单）")
    fills = client.get_fills(test_symbol, side="buy", limit=5)
    print(fills)

    print("\n✅ 所有 API 测试完成")

if __name__ == "__main__":
    test_kucoin_client()