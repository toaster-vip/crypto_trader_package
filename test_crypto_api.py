import requests, time, hmac, hashlib

API_KEY = "s7GzS87EZgTjSzgjG71fQo"  # ✅ 替换为你从 Exchange 获得的
API_SECRET = "cxakp_wZMVxFLmonyfWar4HhVy7f"
BASE_URL = "https://api.crypto.com/v2"

def get_account_summary():
    method = "private/get-account-summary"
    req_id = int(time.time() * 100)
    nonce = int(time.time() * 1000)

    req = {
        "id": req_id,
        "method": method,
        "api_key": API_KEY,
        "params": {},
        "nonce": nonce
    }

    param_string = ""
    for key in sorted(req["params"]):
        param_string += key + str(req["params"][key])

    sig_payload = method + str(req_id) + API_KEY + param_string + str(nonce)
    signature = hmac.new(
        API_SECRET.encode(),
        msg=sig_payload.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()
    req["sig"] = signature

    try:
        response = requests.post(f"{BASE_URL}/{method}", json=req)
        response.raise_for_status()
        print("✅ 响应：", response.json())
    except requests.exceptions.RequestException as e:
        print("❌ 请求失败:", e)
        if e.response is not None:
            print("错误响应:", e.response.text)

get_account_summary()