import time, hmac, hashlib, json
import requests

API_KEY = "WpWVkahrWSCaJfcmvcJgSv"
API_SECRET = "cxakp_FDRiZ8aw9UPogTVTgzzJGv"
BASE_URL = "https://api.crypto.com/v2"

def generate_signature(api_key, method, params, nonce, api_secret):
    payload = {
        "id": 11,
        "method": method,
        "api_key": api_key,
        "params": params,
        "nonce": nonce
    }
    param_str = json.dumps(payload, separators=(',', ':'), sort_keys=True)
    sig = hmac.new(
        api_secret.encode(), 
        msg=param_str.encode(), 
        digestmod=hashlib.sha256
    ).hexdigest()
    payload["sig"] = sig
    return payload

# 调用 private/get-account-summary
nonce = int(time.time() * 1000)
method = "private/get-account-summary"
params = {}

signed_payload = generate_signature(API_KEY, method, params, nonce, API_SECRET)

response = requests.post(f"{BASE_URL}/{method}", json=signed_payload)
print("状态码：", response.status_code)
print("响应：", response.json())