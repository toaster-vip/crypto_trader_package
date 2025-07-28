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
        print(f"🔍 返 回 账 户 信 息 : {acc}")
        currency = acc.get("currency")
        balance = float(acc.get("balance", 0))
        if balance > 0:
            holdings.append({
                "currency": currency,
                "total": balance
            })

    return holdings

def get_supported_symbols():
    # ⚠️ 临时硬编码支持的交易对，避免 public 接口失败造成中断
    print("⚠️ 使用硬编码支持交易对（临时解决方案）")
    return {
        "BTC_USDT",
        "ETH_USDT",
        "SOL_USDT",
        "DOGE_USDT",
        "SHIB_USDT",
        "CRO_USDT",
        "BOME_USDT",
        "TRUMP_USDT",
    }

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
            print(f"⚠️ 跳 过 不 支 持 的 币 种: {h['currency']}")

    return filtered

import requests
from config import BASE_URL

def get_market_data(symbol):
    url = f"{BASE_URL}/public/get-ticker"
    try:
        response = requests.get(url, params={"instrument_name": symbol})
        data = response.json()
    except Exception as e:
        raise Exception(f"网络错误: {e}")

    if data.get("code") != 0:
        raise Exception(f"Ticker API Error: {data.get('message', 'Unknown error')} (code={data.get('code')})")

    result = data.get("result", {})
    if not result or "data" not in result:
        raise Exception("Ticker 返回数据结构异常")

    ticker = result["data"]
    if not isinstance(ticker, dict):
        raise Exception("Ticker 返回数据类型异常，预期为 dict")

    # 示例提取字段，可根据需要补充
    return {
        "price": ticker.get("a"),  # 最新成交价
        "high": ticker.get("h"),
        "low": ticker.get("l"),
        "volume": ticker.get("v"),
        "timestamp": ticker.get("t")
    }