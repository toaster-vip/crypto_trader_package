import time
import hmac
import base64
import hashlib
import requests
import json
from config import CONFIG


class KuCoinClient:
    def __init__(self):
        self.api_key = CONFIG["KUCOIN_API_KEY"]
        self.api_secret = CONFIG["KUCOIN_API_SECRET"]
        self.passphrase = CONFIG["KUCOIN_API_PASSPHRASE"]
        self.base_url = "https://api.kucoin.com"
        self.symbol_limits_cache = {}
        print("🔑 [KuCoinClient] 使用的 KuCoin API KEY:", self.api_key)
        print("📁 [KuCoinClient] config.py 加载成功")
        self._init_symbol_limits_cache()

    def _get_headers(self, method, endpoint, body=""):
        now = str(int(time.time() * 1000))
        str_to_sign = now + method.upper() + endpoint + body
        signature = base64.b64encode(
            hmac.new(self.api_secret.encode(), str_to_sign.encode(), hashlib.sha256).digest()
        ).decode()
        passphrase = base64.b64encode(
            hmac.new(self.api_secret.encode(), self.passphrase.encode(), hashlib.sha256).digest()
        ).decode()

        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": now,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json"
        }

    def _init_symbol_limits_cache(self):
        print("[INFO] ⏳ 正在加载所有交易对限制信息...")
        try:
            url = self.base_url + "/api/v1/symbols"
            response = requests.get(url)
            data = response.json()
            for item in data.get("data", []):
                if item["enableTrading"]:
                    self.symbol_limits_cache[item["symbol"]] = {
                        "minFunds": float(item.get("minFunds", 0)),
                        "minSize": float(item.get("baseMinSize", 0)),
                        "maxSize": float(item.get("baseMaxSize", 1e10)),
                        "stepSize": float(item.get("baseIncrement", 0.000001))
                    }
            print(f"[INFO] ✅ 已缓存 {len(self.symbol_limits_cache)} 个交易对限制参数")
        except Exception as e:
            print(f"[ERROR] 初始化 symbol 限制缓存失败: {e}")

    def get_symbol_limits(self, symbol):
        return self.symbol_limits_cache.get(symbol, None)

    def get_account_holdings(self):
        endpoint = "/api/v1/accounts"
        url = self.base_url + endpoint
        headers = self._get_headers("GET", endpoint)
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            balances = {}
            for acc in data.get("data", []):
                if acc.get("type") != "main":
                    continue
                currency = acc["currency"]
                balance = float(acc.get("available") or acc.get("balance") or 0)
                if balance > 0:
                    balances[currency] = balance
            return balances
        except Exception as e:
            print(f"[ERROR] 获取账户持仓失败: {e}")
            return {}

    def get_supported_symbols(self):
        return list(self.symbol_limits_cache.keys())

    def get_market_data(self, symbol):
        url = self.base_url + f"/api/v1/market/stats?symbol={symbol}"
        try:
            response = requests.get(url)
            data = response.json()
            ticker = data.get("data", {})
            return {
                "price": float(ticker.get("last", 0.0)),
                "open": float(ticker.get("open", 0.0)),
                "high": float(ticker.get("high", 0.0)),
                "low": float(ticker.get("low", 0.0)),
                "vol": float(ticker.get("vol", 0.0)),
            }
        except Exception as e:
            print(f"[ERROR] 获取行情失败 {symbol}: {e}")
            return {}

    def place_order(self, symbol, side, size, price=None):
        endpoint = "/api/v1/orders"
        url = self.base_url + endpoint
        order_type = "market" if price is None else "limit"
        body_dict = {
            "clientOid": str(int(time.time() * 1000)),
            "side": side,
            "symbol": symbol,
            "type": order_type
        }

        if order_type == "market":
            if side == "buy":
                # 市价买单需指定资金数量（USDT）
                body_dict["funds"] = str(size)
            else:
                # 市价卖单需指定数量（币数量）
                body_dict["size"] = str(size)
        else:
            # 限价单需提供 size 和 price
            body_dict["size"] = str(size)
            body_dict["price"] = str(price)

        body = json.dumps(body_dict)
        headers = self._get_headers("POST", endpoint, body)

        try:
            response = requests.post(url, headers=headers, data=body)
            result = response.json()
            if result.get("code") == "200000":
                print(f"[✅] 下单成功（{side} {symbol}）: {result['data']['orderId']}")
                return result["data"]["orderId"]
            else:
                print(f"[ERROR] 下单失败: {result}")
                return None
        except Exception as e:
            print(f"[ERROR] 下单请求异常: {e}")
            return None

    def get_symbol_price(self, symbol):
        url = f"{self.base_url}/api/v1/market/orderbook/level1"
        params = {"symbol": symbol}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            return float(data["data"]["price"])
        except Exception as e:
            print(f"[ERROR] 获取价格失败 {symbol}: {e}")
            return None

    def get_timestamp(self):
        try:
            url = self.base_url + "/api/v1/timestamp"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return int(data["data"])
        except Exception as e:
            print(f"[ERROR] 获取时间戳失败: {e}")
            return int(time.time() * 1000)

    def redeem_autoearn(self, currency="USDT", amount=None):
        endpoint = "/api/v1/earn/account/redeem"
        url = self.base_url + endpoint
        body_dict = {
            "currency": currency
        }
        if amount:
            body_dict["redeemAmount"] = str(amount)
        body = json.dumps(body_dict)
        headers = self._get_headers("POST", endpoint, body)
        try:
            response = requests.post(url, headers=headers, data=body)
            res_json = response.json()
            if res_json.get("code") == "200000":
                print(f"[INFO] 已提交 Auto Earn 赎回请求（{currency}）")
                return True
            else:
                print(f"[WARN] Auto Earn 赎回失败: {res_json}")
                return False
        except Exception as e:
            print(f"[ERROR] Auto Earn 请求失败: {e}")
            return False

    def get_trade_account_balance(self, currency="USDT"):
        endpoint = "/api/v1/accounts"
        url = self.base_url + endpoint
        headers = self._get_headers("GET", endpoint)
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            for acc in data.get("data", []):
                if acc.get("type") == "trade" and acc.get("currency") == currency:
                    balance = float(acc.get("available") or 0)
                    print(f"[🔍] 交易账户 {currency} 可用余额: {balance}")
                    return balance
            print(f"[WARN] 未找到交易账户 {currency} 余额信息")
            return 0.0
        except Exception as e:
            print(f"[ERROR] 获取交易账户余额失败: {e}")
            return 0.0

    def transfer_to_trade_account(self, currency="USDT", amount=1.0):
        endpoint = "/api/v2/accounts/inner-transfer"
        url = self.base_url + endpoint
        body_dict = {
            "clientOid": str(int(time.time() * 1000)),
            "currency": currency,
            "from": "main",
            "to": "trade",
            "amount": str(amount)
        }
        body = json.dumps(body_dict)
        headers = self._get_headers("POST", endpoint, body)
        try:
            response = requests.post(url, headers=headers, data=body)
            data = response.json()
            if data.get("code") == "200000":
                print(f"[✅] 已从主账户转入 {amount} {currency} 到交易账户")
                return True
            else:
                print(f"[ERROR] 转账失败: {data}")
                return False
        except Exception as e:
            print(f"[ERROR] 转账请求异常: {e}")
            return False