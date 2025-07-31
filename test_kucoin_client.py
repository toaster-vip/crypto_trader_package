import time
from kucoin_api import KuCoinClient  # ✅ 引入你的 KuCoinClient 类

def test_kucoin_client():
    client = KuCoinClient()

    print("=== 🔍 测试 KuCoin API 功能 ===")

    # 1. 获取账户持仓
    print("\n[1] 获取账户持仓：")
    holdings = client.get_account_holdings()
    print(holdings)

    # ✅ 1.1 获取主账户中 USDT 的可用余额
    print("\n[1.1] 获取主账户中 USDT 可用余额：")
    usdt_balance = holdings.get("USDT", 0.0)
    print(f"当前 USDT 余额：{usdt_balance} USDT")

    # ✅ 1.2 获取交易账户 USDT 余额，并尝试从主账户转入 1 USDT
    print("\n[1.2] 获取交易账户 USDT 余额并尝试转入资金：")
    main_usdt = holdings.get("USDT", 0)
    print(f"主账户 USDT: {main_usdt}")

    trade_usdt = client.get_trade_account_balance("USDT")
    print(f"交易账户 USDT: {trade_usdt}")

    if main_usdt > 1:
        success = client.transfer_to_trade_account("USDT", 1.0)
        if success:
            print("✅ 成功转入 1.0 USDT 到交易账户")

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

    print("\n✅ 所有 API 测试完成")

if __name__ == "__main__":
    test_kucoin_client()