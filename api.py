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
    """
    从账户余额中提取所有有资产或可交易的币种列表
    """
    try:
        url = f"{BASE_URL}/private/get-account-summary"
        params = {
            "api_key": API_KEY,
            "req_time": int(time.time() * 1000),
        }
        param_str = urlencode(sorted(params.items()))
        to_sign = f"{param_str}"
        sign = hmac.new(
            bytes(API_SECRET.encode('utf-8')),
            msg=bytes(to_sign.encode('utf-8')),
            digestmod=hashlib.sha256
        ).hexdigest()
        params["sig"] = sign

        resp = requests.post(url, json=params)
        result = resp.json()

        symbols = []
        for asset in result.get("result", {}).get("accounts", []):
            currency = asset.get("currency")
            total = float(asset.get("available", 0)) + float(asset.get("balance", 0))
            if total > 0 or currency in ["USDT", "USDC"]:  # 保留可用资金币种
                symbols.append(currency)

        return sorted(list(set(symbols)))
    except Exception as e:
        print("[ERROR] 获取币种失败：", e)
        return []