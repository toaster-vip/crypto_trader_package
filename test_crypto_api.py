import time
import base64
import hmac
import hashlib
import requests

# ✅ 替换为你的 KuCoin API 信息
API_KEY = "688906b7dffe710001e697de"
API_SECRET = "11a7e8e2-11f8-4602-a72d-7788c31"
API_PASSPHRASE = "ilovesophia"

API_BASE = "https://api.kucoin.com"

def get_headers(endpoint, method="GET", body=""):
    now = str(int(time.time() * 1000))
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
        "KC-API-TIMESTAMP": now,
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

def check_all_usdt_accounts():
    endpoint = "/api/v1/accounts"
    url = API_BASE + endpoint
    headers = get_headers(endpoint)
    print("🔍 检查所有账户中的 USDT 分布...\n")
    try:
        resp = requests.get(url, headers=headers)
        data = resp.json()
        if data.get("code") != "200000":
            print("[ERROR] 无法获取账户信息:", data)
            return
        found = False
        for acc in data.get("data", []):
            if acc["currency"] == "USDT":
                found = True
                print(f"账户类型: {acc['type']:<10} | 可用: {acc['available']:<12} | 总余额: {acc['balance']}")
        if not found:
            print("❌ 没有找到任何 USDT 资产")
    except Exception as e:
        print(f"[ERROR] 请求失败: {e}")

if __name__ == "__main__":
    print("✅ KuCoin API 测试开始\n")
    test_get_accounts()
    print("-" * 50)
    test_get_balance("USDT")
    print("-" * 50)
    test_get_price("BTC-USDT")
    print("-" * 50)
    check_all_usdt_accounts()
    print("\n✅ 测试结束")