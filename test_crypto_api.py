import time
import base64
import hmac
import hashlib
import requests
import json

# ✅ KuCoin API 配置信息
API_KEY = "688990c9c714e80001ef1a2c"
API_SECRET = "473367a6-af01-48d2-8b78-2817ab879dc1"
API_PASSPHRASE = "ilovesophia"

API_BASE = "https://api.kucoin.com"

def get_headers(endpoint, method="GET", body=""):
    now = int(time.time() * 1000)
    str_to_sign = f"{now}{method.upper()}{endpoint}{body}"
    signature = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), str_to_sign.encode('utf-8'), hashlib.sha256).digest()
    ).decode()

    passphrase = base64.b64encode(
        hmac.new(API_SECRET.encode('utf-8'), API_PASSPHRASE.encode('utf-8'), hashlib.sha256).digest()
    ).decode()

    return {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": str(now),
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }

def test_get_accounts():
    endpoint = "/api/v1/accounts"
    url = API_BASE + endpoint
    headers = get_headers(endpoint)
    print("▶ 请求账户资产列表中...")
    resp = requests.get(url, headers=headers)
    print(resp.json())

def test_get_balance_all(currency="USDT"):
    endpoint = "/api/v1/accounts"
    url = API_BASE + endpoint
    headers = get_headers(endpoint)
    print(f"▶ 检查所有账户中的 {currency} 分布...")
    resp = requests.get(url, headers=headers)
    data = resp.json()

    if data.get("code") != "200000":
        print("[❌] 获取失败:", data)
        return 0.0

    total = 0.0
    for acc in data["data"]:
        if acc["currency"] == currency and acc["type"] == "trade":
            print(f"  📌 {acc['type']} 账户: 可用 {acc['available']}")
            total += float(acc["available"])

    print(f"💰 总共可用 {currency}: {total:.4f}")
    return total

def test_get_price(symbol="XLM-USDT"):
    url = f"{API_BASE}/api/v1/market/orderbook/level1?symbol={symbol}"
    print(f"▶ 获取 {symbol} 实时价格中...")
    resp = requests.get(url)
    data = resp.json()
    print(data)
    if data.get("code") == "200000":
        return float(data["data"]["price"])
    return None

def place_order(symbol, side, size, price=None):
    endpoint = "/api/v1/orders"
    url = API_BASE + endpoint

    order = {
        "clientOid": str(int(time.time() * 1000)),
        "side": side,
        "symbol": symbol,
        "type": "market",
        "size": size
    }

    body = json.dumps(order)
    headers = get_headers(endpoint, method="POST", body=body)
    print(f"▶ 发起 {side} 市价单 {symbol} 数量={size} ...")
    resp = requests.post(url, headers=headers, data=body)
    print(resp.json())

def test_buy_sell():
    symbol = "XLM-USDT"
    usdt_amount = 1.0

    price = test_get_price(symbol)
    if not price:
        print("[❌] 获取价格失败")
        return

    # 保守估算手续费后买入数量
    qty = round((usdt_amount * 0.999) / price, 2)
    print(f"🛒 以市价买入 {qty} 个 {symbol.split('-')[0]} ≈ 1 USDT")

    place_order(symbol, "buy", str(qty))
    time.sleep(5)

    print(f"🛒 5秒后以市价卖出 {qty} 个 {symbol.split('-')[0]}")
    place_order(symbol, "sell", str(qty))

if __name__ == "__main__":
    print("✅ KuCoin API 测试开始")
    test_get_accounts()
    print("-" * 50)
    test_get_balance_all("USDT")
    print("-" * 50)
    test_get_price("BTC-USDT")
    print("-" * 50)
    test_buy_sell()
    print("✅ 测试结束")