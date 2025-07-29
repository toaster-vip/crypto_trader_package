# test_apis.py
import time
import hmac
import hashlib
import requests

# === 你的真实 API 信息（Crypto.com Exchange API）===
API_KEY = "s7GzS87EZgTjSzgjG71fQo"
API_SECRET = "cxakp_wZMVxFLmonyfWar4HhVy7f"


# ===============================
# 🔸 Part 1: Exchange V1 API
# ===============================
def test_exchange_v1():
    print("\n=== 🔸 Exchange V1 API 测试 ===")
    base_url = "https://api.crypto.com/exchange/v1"

    def sign(req):
        param_str = "".join([f"{k}{v}" for k, v in sorted(req['params'].items())])
        sig_payload = req['method'] + str(req['id']) + API_KEY + param_str + str(req['nonce'])
        sig = hmac.new(API_SECRET.encode(), sig_payload.encode(), hashlib.sha256).hexdigest()
        req['sig'] = sig
        return req

    def send(method, params=None):
        req = {
            "id": int(time.time() * 1000),
            "method": method,
            "api_key": API_KEY,
            "params": params or {},
            "nonce": int(time.time() * 1000)
        }
        signed = sign(req)
        resp = requests.post(f"{base_url}/{method}", json=signed)
        return resp.json()

    # 📌 获取账户信息
    summary = send("private/get-account-summary")
    print("账户信息:", summary)

    # 📌 获取交易对列表
    try:
        instruments = requests.get(f"{base_url}/public/get-instruments").json()
        print("交易对数量:", len(instruments.get("result", {}).get("instruments", [])))
    except Exception as e:
        print("[ERROR] 获取交易对失败:", e)

    # 📌 获取 BTC_USDT 最新行情
    try:
        ticker = requests.get(f"{base_url}/public/get-ticker", params={"instrument_name": "BTC_USDT"}).json()
        print("BTC_USDT 最新价格:", ticker.get("result", {}).get("data", {}))
    except Exception as e:
        print("[ERROR] 获取 BTC_USDT 价格失败:", e)


# ===============================
# 🔹 Part 2: App V2 API
# ===============================
def test_app_v2():
    print("\n=== 🔹 App V2 API 测试 ===")
    base_url = "https://api.crypto.com/v2"

    def sign(req):
        param_str = "".join([f"{k}{v}" for k, v in sorted(req['params'].items())])
        sig_payload = req['method'] + str(req['id']) + API_KEY + param_str + str(req['nonce'])
        sig = hmac.new(API_SECRET.encode(), sig_payload.encode(), hashlib.sha256).hexdigest()
        req['sig'] = sig
        return req

    def send(method, params=None):
        req = {
            "id": int(time.time() * 1000),
            "method": method,
            "api_key": API_KEY,
            "params": params or {},
            "nonce": int(time.time() * 1000)
        }
        signed = sign(req)
        resp = requests.post(f"{base_url}/{method}", json=signed)
        return resp.json()

    # 📌 获取账户信息
    summary = send("private/get-account-summary")
    print("账户信息:", summary)

    # 📌 获取交易对列表
    try:
        instruments = requests.get(f"{base_url}/public/get-instruments").json()
        print("交易对数量:", len(instruments.get("result", {}).get("instruments", [])))
    except Exception as e:
        print("[ERROR] 获取交易对失败:", e)

    # 📌 获取 BTC_USDT 最新行情
    try:
        ticker = requests.get(f"{base_url}/public/get-ticker", params={"instrument_name": "BTC_USDT"}).json()
        print("BTC_USDT 最新价格:", ticker.get("result", {}).get("data", {}))
    except Exception as e:
        print("[ERROR] 获取 BTC_USDT 价格失败:", e)


# ===============================
# ✅ 主入口
# ===============================
if __name__ == "__main__":
    test_exchange_v1()
    test_app_v2()