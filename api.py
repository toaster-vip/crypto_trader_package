import time
import hmac
import hashlib
import requests
import json
from config import API_KEY, API_SECRET, BASE_URL

def _signed_post(method, params=None):
    if params is None:
        params = {}

    req = {
        "id": int(time.time() * 1000),
        "method": method,
        "api_key": API_KEY,
        "params": params,
        "nonce": int(time.time() * 1000)
    }

    param_string = ""
    for key in sorted(req["params"]):
        param_string += key + str(req["params"][key])

    to_sign = req["method"] + str(req["id"]) + req["api_key"] + param_string + str(req["nonce"])
    req["sig"] = hmac.new(
        API_SECRET.encode(),
        msg=to_sign.encode(),
        digestmod=hashlib.sha256
    ).hexdigest()

    response = requests.post(f"{BASE_URL}/{method}", json=req)
    data = response.json()

    if data.get("code") != 0:
        raise Exception(f"API Error: {data.get('message', 'Unknown error')}")

    return data["result"]

def get_account_holdings():
    result = _signed_post("private/get-account-summary")
    balances = result.get("accounts", [])
    holdings = []

    for acc in balances:
        print("🔍 返回账户信息:", acc)  # ✅ 调试用
        total_balance = acc.get("total_balance")
        currency = acc.get("currency")

        if total_balance is not None:
            try:
                if float(total_balance) > 0:
                    holdings.append({
                        "currency": currency,
                        "total": float(total_balance)
                    })
            except ValueError:
                print(f"⚠️ 无法解析余额: {total_balance} (币种: {currency})")
        else:
            print(f"⚠️ 跳过未含 total_balance 的账户: {acc}")

    return holdings

def get_all_symbols():
    result = _signed_post("private/get-account-summary")
    balances = result.get("accounts", [])
    usdt_symbols = []

    for acc in balances:
        symbol = f"{acc['currency']}_USDT"
        usdt_symbols.append(acc["currency"])

    return list(set(usdt_symbols))

def get_market_data(symbol):
    # symbol: e.g. BTC_USDT
    resp = requests.get(f"{BASE_URL}/public/get-ticker", params={"instrument_name": symbol})
    data = resp.json()

    if data.get("code") != 0:
        raise Exception(f"Market API Error: {data.get('message', 'Unknown error')}")

    ticker = data["result"]["data"]
    return {
        "price": float(ticker["a"])  # ask price
    }