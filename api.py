import requests, time, hmac, hashlib
from config import CONFIG

def sign_request(payload):
    t = int(time.time() * 1000)
    payload.update({"api_key": CONFIG["API_KEY"], "req_time": t})
    data = '|'.join(f"{k}={payload[k]}" for k in sorted(payload))
    payload["sig"] = hmac.new(CONFIG["API_SECRET"].encode(), data.encode(), hashlib.sha256).hexdigest()
    return payload

def get_market_data(symbol):
    params = sign_request({"instrument_name": symbol})
    resp = requests.get(CONFIG["BASE_URL"] + "/public/get-ticker", params=params)
    return resp.json()