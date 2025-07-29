import time
import hmac
import hashlib
import requests
import json

API_KEY = "s7GzS87EZgTjSzgjG71fQo"
API_SECRET = "cxakp_wZMVxFLmonyfWar4HhVy7f"
BASE_URL = "https://api.crypto.com/v2"

def generate_signature(api_key, api_secret, method, params, nonce):
    param_str = ''
    if params:
        param_str = ''.join(f"{key}{params[key]}" for key in sorted(params))
    sig_payload = method + str(nonce) + api_key + param_str
    signature = hmac.new(
        bytes(api_secret, 'utf-8'),
        msg=bytes(sig_payload, 'utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    return signature

def private_request(method, params=None):
    url = f"{BASE_URL}/{method}"
    nonce = int(time.time() * 1000)
    body = {
        "id": nonce,
        "method": method,
        "api_key": API_KEY,
        "nonce": nonce,
        "params": params or {}
    }
    sig = generate_signature(API_KEY, API_SECRET, method, body["params"], nonce)
    body["sig"] = sig

    headers = {"Content-Type": "application/json"}
    response = requests.post(url, headers=headers, data=json.dumps(body))

    try:
        res = response.json()
        print(f"\n📡 请求成功: {method}")
        print(json.dumps(res, indent=2))
    except Exception as e:
        print(f"\n❌ 请求失败: {method}")
        print(f"HTTP Status: {response.status_code}")
        print(response.text)

# 测试调用
if __name__ == "__main__":
    private_request("private/get-account-summary")