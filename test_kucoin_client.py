import time
from kucoin_api import KuCoinClient

# 这里直接硬编码 API 信息，优先用于测试
class KuCoinClientTest(KuCoinClient):
    def __init__(self):
        self.api_key = "6894b5c7dffe710001e70b3e"
        self.api_secret = "b227a741-6a74-4ac5-9445-4a6c256adedd"
        self.passphrase = "1234567"
        self.base_url = "https://api.kucoin.com"
        self.simulate = False
        self.symbol_limits_cache = {}
        self._init_symbol_limits_cache()
        print("🔑 [KuCoinClient] 使用硬编码API KEY:", self.api_key[:5] + "***")
        print("📁 [KuCoinClientTest] API Key硬编码测试模式加载成功")

def test_kucoin_client():
    client = KuCoinClientTest()

    print("=== 🔍 测试 KuCoin API 功能 ===")

    # 1. 获取账户持仓
    print("\n[1] 获取账户持仓：")
    holdings = client.get_account_holdings()
    print(holdings)

    print("\n[2] 获取支持交易的 USDT 对：")
    symbols = client.get_supported_symbols()
    print(f"共 {len(symbols)} 个交易对，示例：", symbols[:5])

    # 3. 获取实时价格
    test_symbol = "XLM-USDT"
    print(f"\n[3] 获取当前价格：{test_symbol}")
    price = client.get_symbol_price(test_symbol)
    print(f"{test_symbol} 当前价格: {price}")

    # 4. 测试历史成交明细 fills（只取最新5条买单）
    print(f"\n[4] 获取历史成交明细 fills（测试币种：{test_symbol}，只取最新5条买单）")
    fills = client.get_fills(test_symbol, side="buy", limit=5)
    print(fills)

    print("\n✅ 所有 API 测试完成")

if __name__ == "__main__":
    test_kucoin_client()