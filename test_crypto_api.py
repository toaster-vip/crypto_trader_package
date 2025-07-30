import time
import base64
import hmac
import hashlib
import requests

# ✅ 来自 config.py 中的 API 配置
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

def test_get_balance(currency="USDT"):
    endpoint = f"/api/v1/accounts?currency={currency}"
    url = API_BASE + endpoint
    headers = get_headers(endpoint)
    print(f"▶ 获取 {currency} 余额中...")
    resp = requests.get(url, headers=headers)
    print(resp.json())

def test_get_price(symbol="BTC-USDT"):
    url = f"{API_BASE}/api/v1/market/orderbook/level1?symbol={symbol}"
    print(f"▶ 获取 {symbol} 实时价格中...")
    resp = requests.get(url)
    print(resp.json())

if __name__ == "__main__":
    print("✅ KuCoin API 测试开始")
    test_get_accounts()
    print("-" * 50)
    test_get_balance("USDT")
    print("-" * 50)
    test_get_price("BTC-USDT")
    print("✅ 测试结束")