import time
import hmac
import hashlib
import requests
import json
from config import API_KEY, API_SECRET, BASE_URL

# ✅ 签名并发起 POST 请求
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

# ✅ 获取账户真实持仓
def get_account_holdings():
    result = _signed_post("private/get-account-summary")
    balances = result.get("accounts", [])
    holdings = []

    for acc in balances:
        print(f"\033[36m🔍 返 回 账 户 信 息 : {acc}\033[0m")
        currency = acc.get("currency")
        balance = float(acc.get("balance", 0))
        if balance > 0:
            holdings.append({
                "currency": currency,
                "total": balance
            })

    return holdings

# ✅ 获取所有支持 USDT 交易对
def get_supported_symbols():
    url = f"{BASE_URL}/public/get-instruments"
    try:
        response = requests.get(url, params={"instrument_type": "SPOT"})
        data = response.json()
    except Exception as e:
        print(f"\033[91m❌ 获取币种列表失败（网络或解析错误）：{e}\033[0m")
        return set()

    if data.get("code") != 0:
        print(f"\033[91m❌ 获取币种列表失败：{data.get('message', 'Unknown error')} (code={data.get('code')})\033[0m")
        return set()

    instruments = data.get("result", {}).get("instruments", [])
    usdt_pairs = set()

    for item in instruments:
        try:
            if item.get("quote_currency") == "USDT":
                usdt_pairs.add(item["instrument_name"])
        except:
            continue

    print(f"\033[32m✅ 共识别 {len(usdt_pairs)} 个支持 USDT 的币种交易对\033[0m")
    return usdt_pairs

# ✅ 从持仓中筛选出可交易币种
def filter_valid_holdings(holdings):
    valid_symbols = get_supported_symbols()
    filtered = []

    for h in holdings:
        symbol = f"{h['currency']}_USDT"
        if symbol in valid_symbols:
            filtered.append({
                "symbol": symbol,
                "amount": h["total"]
            })
        else:
            print(f"\033[90m⚠️ 跳 过 不 支 持 的 币 种: {h['currency']}\033[0m")

    return filtered

# ✅ 获取市场行情
def get_market_data(symbol):
    try:
        resp = requests.get(f"{BASE_URL}/public/get-ticker", params={"instrument_name": symbol})
        data = resp.json()
    except Exception as e:
        raise Exception(f"Market API Request Error: {e}")

    if data.get("code") != 0:
        raise Exception(f"Market API Error: {data.get('message', 'Unknown error')}")

    ticker = data["result"]["data"]
    return {
        "price": float(ticker["a"])  # ask price
    }