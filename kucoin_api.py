import requests
import time
import hmac
import base64
import hashlib
import json
from decimal import Decimal, ROUND_DOWN
from threading import Lock

from config import CONFIG

API_KEY = CONFIG["KUCOIN_API_KEY"]
API_SECRET = CONFIG["KUCOIN_API_SECRET"]
API_PASSPHRASE = CONFIG["KUCOIN_API_PASSPHRASE"]

API_BASE_URL = "https://api.kucoin.com"

# 用于 symbol 限制缓存，防止重复请求
_symbol_rules_cache = None
_symbol_rules_lock = Lock()

# 获取当前毫秒时间戳
def get_timestamp():
    return str(int(time.time() * 1000))

# 生成 KuCoin API 签名头
def _get_headers(method, endpoint, body=""):
    now = get_timestamp()
    str_to_sign = f"{now}{method.upper()}{endpoint}{body}"
    signature = base64.b64encode(
        hmac.new(API_SECRET.encode("utf-8"), str_to_sign.encode("utf-8"), hashlib.sha256).digest()
    ).decode()
    passphrase = base64.b64encode(
        hmac.new(API_SECRET.encode("utf-8"), API_PASSPHRASE.encode("utf-8"), hashlib.sha256).digest()
    ).decode()
    return {
        "KC-API-KEY": API_KEY,
        "KC-API-SIGN": signature,
        "KC-API-TIMESTAMP": now,
        "KC-API-PASSPHRASE": passphrase,
        "KC-API-KEY-VERSION": "2",
        "Content-Type": "application/json"
    }

# GET请求工具函数，带异常/重试
def kucoin_get(endpoint, params=None, max_retry=3):
    url = API_BASE_URL + endpoint
    for i in range(max_retry):
        try:
            headers = _get_headers("GET", endpoint)
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "200000":
                    return data["data"]
                else:
                    print(f"[KuCoin API] Error code {data.get('code')}: {data.get('msg')}")
            elif resp.status_code == 429:
                print("[KuCoin API] 429 Too Many Requests, sleep and retry...")
                time.sleep(2 * (i+1))
            else:
                print(f"[KuCoin API] HTTP error: {resp.status_code}, content: {resp.text}")
        except Exception as ex:
            print(f"[KuCoin API] Exception: {ex}")
        time.sleep(1 + i)
    return None

# POST请求工具函数
def kucoin_post(endpoint, payload, max_retry=3):
    url = API_BASE_URL + endpoint
    body = json.dumps(payload) if payload else ""
    for i in range(max_retry):
        try:
            headers = _get_headers("POST", endpoint, body)
            resp = requests.post(url, headers=headers, data=body, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("code") == "200000":
                    return data["data"]
                else:
                    print(f"[KuCoin API] Error code {data.get('code')}: {data.get('msg')}")
            elif resp.status_code == 429:
                print("[KuCoin API] 429 Too Many Requests, sleep and retry...")
                time.sleep(2 * (i+1))
            else:
                print(f"[KuCoin API] HTTP error: {resp.status_code}, content: {resp.text}")
        except Exception as ex:
            print(f"[KuCoin API] Exception: {ex}")
        time.sleep(1 + i)
    return None

# 获取交易所所有可交易币对的规则（缓存机制）
def get_symbol_rules():
    global _symbol_rules_cache
    with _symbol_rules_lock:
        if _symbol_rules_cache is None:
            print("[KuCoin] 拉取币对交易规则（仅第一次）")
            data = kucoin_get("/api/v1/symbols")
            if not data or "symbols" not in data:
                print("[KuCoin] 拉取币对规则失败！")
                _symbol_rules_cache = {}
            else:
                # 用dict方便查找
                _symbol_rules_cache = {item["symbol"]: item for item in data["symbols"]}
        return _symbol_rules_cache

# 获取主账户余额（包含USDT等所有币）
def get_main_account_balances():
    data = kucoin_get("/api/v1/accounts", {"type": "main"})
    balances = {}
    if data and "items" in data:
        for acc in data["items"]:
            balances[acc["currency"]] = Decimal(acc["available"])
    return balances

# 获取交易账户余额
def get_trade_account_balances():
    data = kucoin_get("/api/v1/accounts", {"type": "trade"})
    balances = {}
    if data and "items" in data:
        for acc in data["items"]:
            balances[acc["currency"]] = Decimal(acc["available"])
    return balances

# 主账户向交易账户转账
def transfer_to_trade_account(currency, amount):
    payload = {
        "clientOid": str(int(time.time() * 100000)),
        "currency": currency,
        "from": "main",
        "to": "trade",
        "amount": str(amount)
    }
    result = kucoin_post("/api/v2/accounts/inner-transfer", payload)
    if result:
        print(f"[KuCoin] 已自动转账 {amount} {currency} 从主账户→交易账户")
        return True
    print(f"[KuCoin] 主账户转账失败：{currency} {amount}")
    return False

# 查询所有支持USDT交易对的币种
def get_supported_symbols():
    rules = get_symbol_rules()
    # 只要 quoteCurrency=USDT 并且启用状态
    return [
        s for s, item in rules.items()
        if item["quoteCurrency"] == "USDT" and item["enableTrading"] == True
    ]

# 获取现价（ticker最新价）
def get_symbol_price(symbol):
    data = kucoin_get(f"/api/v1/market/orderbook/level1", {"symbol": symbol})
    if data and "price" in data:
        return Decimal(data["price"])
    return None

# 获取最新K线（分钟线）
def get_klines(symbol, ktype="1min", limit=100):
    data = kucoin_get("/api/v1/market/candles", {
        "symbol": symbol,
        "type": ktype,
        "reverse": "true",
        "limit": str(limit)
    })
    if data and isinstance(data, list):
        return [
            {
                "timestamp": int(item[0]),
                "open": float(item[1]),
                "close": float(item[2]),
                "high": float(item[3]),
                "low": float(item[4]),
                "volume": float(item[5])
            }
            for item in data
        ]
    return []

# 下单（市价或限价，严格用config参数）
def place_order(symbol, side, size, price=None, type="market"):
    """
    市价单需传 size=数量（买币时用资金数量），限价单需传price
    """
    payload = {
        "clientOid": str(int(time.time() * 100000)),
        "side": side,
        "symbol": symbol,
        "type": type,
        "size": str(size)
    }
    if type == "limit" and price:
        payload["price"] = str(price)
    result = kucoin_post("/api/v1/orders", payload)
    if result:
        print(f"[KuCoin] 下单成功: {side} {size} {symbol} @ {price if price else '市价'}")
        return result
    else:
        print(f"[KuCoin] 下单失败: {side} {size} {symbol}")
        return None

# 校验下单符号限制（最小金额/数量/步进量等）
def check_order_limits(symbol, funds=None, size=None):
    rules = get_symbol_rules().get(symbol)
    if not rules:
        print(f"[KuCoin] 未找到 {symbol} 的交易规则")
        return False

    # 最小下单金额、最小数量
    min_funds = Decimal(rules.get("minFunds", "0.0"))
    min_size = Decimal(rules.get("minSize", "0.0"))
    max_size = Decimal(rules.get("maxSize", "100000000"))
    base_increment = Decimal(rules.get("baseIncrement", "0.0001"))
    price_increment = Decimal(rules.get("priceIncrement", "0.0001"))

    if funds is not None and funds < min_funds:
        print(f"[KuCoin] 下单金额低于最小要求: {funds} < {min_funds}")
        return False
    if size is not None and size < min_size:
        print(f"[KuCoin] 下单数量低于最小要求: {size} < {min_size}")
        return False
    if size is not None and size > max_size:
        print(f"[KuCoin] 下单数量超出最大限制: {size} > {max_size}")
        return False
    # 检查数量/价格是否为步进量倍数
    if size is not None and (size % base_increment != 0):
        print(f"[KuCoin] 下单数量 {size} 非步进量 {base_increment} 的倍数")
        return False

    return True

# 获取币种24小时成交量
def get_24h_volume(symbol):
    data = kucoin_get(f"/api/v1/market/stats", {"symbol": symbol})
    if data and "volValue" in data:
        return float(data["volValue"])
    return None