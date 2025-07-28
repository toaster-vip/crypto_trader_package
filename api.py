import requests
from config import BASE_URL, API_KEY, API_SECRET
import hmac, hashlib, time, json

def get_headers(payload: dict):
    t = str(int(time.time() * 1000))
    msg = t + API_KEY + json.dumps(payload)
    sign = hmac.new(
        bytes(API_SECRET, 'utf-8'),
        msg=bytes(msg, 'utf-8'),
        digestmod=hashlib.sha256
    ).hexdigest()
    return {
        'Content-Type': 'application/json',
        'X-MBX-APIKEY': API_KEY,
        'X-CREX-APIKEY': API_KEY,
        'X-SIGNATURE': sign,
        'X-TIMESTAMP': t
    }

def get_market_data(symbol: str):
    url = f"{BASE_URL}/public/get-ticker"
    payload = {"instrument_name": f"{symbol}_USDT"}
    try:
        resp = requests.post(url, json=payload)
        result = resp.json()
        return {
            "price": result["result"]["data"]["a"]  # ask 价格
        }
    except Exception:
        return {}

def get_all_symbols():
    url = f"{BASE_URL}/public/get-instruments"
    payload = {"instrument_type": "SPOT"}
    try:
        resp = requests.post(url, json=payload)
        result = resp.json()
        symbols = []
        for item in result.get("result", {}).get("instruments", []):
            if item["quote_currency"] == "USDT" and item["instrument_name"].endswith("USDT"):
                base = item["base_currency"]
                if base.isalpha() and len(base) <= 10:
                    symbols.append(base)
        return sorted(list(set(symbols)))
    except Exception:
        return []