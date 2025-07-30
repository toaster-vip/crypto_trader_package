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

    def get_account_holdings(self):
        endpoint = "/api/v1/accounts"
        url = self.base_url + endpoint
        headers = self._get_headers("GET", endpoint)
        try:
            response = requests.get(url, headers=headers)
            data = response.json()
            balances = {}
            for acc in data.get("data", []):
                currency = acc["currency"]
                balance = float(acc["available"])
                if balance > 0:
                    balances[currency] = balance
            return balances
        except Exception as e:
            print(f"[ERROR] 获取账户持仓失败: {e}")
            return {}

    def get_supported_symbols(self):
        url = self.base_url + "/api/v1/symbols"
        try:
            response = requests.get(url)
            data = response.json()
            pairs = data.get("data", [])
            usdt_symbols = [
                p["symbol"]
                for p in pairs
                if p["quoteCurrency"] == "USDT" and p["enableTrading"]
            ]
            return usdt_symbols
        except Exception as e:
            print(f"[ERROR] 获取交易对失败: {e}")
            return []

    def get_market_data(self, symbol):
        url = self.base_url + f"/api/v1/market/stats?symbol={symbol}"
        try:
            response = requests.get(url)
            data = response.json()
            ticker = data.get("data", {})
            return {
                "price": float(ticker["last"]),
                "open": float(ticker["open"]),
                "high": float(ticker["high"]),
                "low": float(ticker["low"]),
                "vol": float(ticker["vol"]),
            }
        except Exception as e:
            print(f"[ERROR] 获取行情失败: {e}")
            return {}

    def place_order(self, symbol, side, size, price=None):
        endpoint = "/api/v1/orders"
        url = self.base_url + endpoint
        order_type = "market" if price is None else "limit"
        body_dict = {
            "clientOid": str(int(time.time() * 1000)),
            "side": side,
            "symbol": symbol,
            "type": order_type,
            "size": str(size)
        }
        if price:
            body_dict["price"] = str(price)

        body = json.dumps(body_dict)
        headers = self._get_headers("POST", endpoint, body)
        try:
            response = requests.post(url, headers=headers, data=body)
            result = response.json()
            if result.get("code") == "200000":
                return result["data"]["orderId"]
            else:
                print(f"[ERROR] 下单失败: {result}")
                return None
        except Exception as e:
            print(f"[ERROR] 下单请求失败: {e}")
            return None

    def get_symbol_price(self, symbol):
        """
        获取某个交易对的最新成交价（如 PROM-USDT）
        """
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
        """
        获取当前 KuCoin 服务器时间戳（毫秒）
        """
        try:
            url = self.base_url + "/api/v1/timestamp"
            response = requests.get(url)
            response.raise_for_status()
            data = response.json()
            return int(data["data"])
        except Exception as e:
            print(f"[ERROR] 获取时间戳失败: {e}")
            return int(time.time() * 1000)