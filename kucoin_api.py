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
                    try:
                        self.symbol_limits_cache[item["symbol"]] = {
                            "minFunds": float(item.get("minFunds") or 0),
                            "minSize": float(item.get("baseMinSize") or 0),
                            "maxSize": float(item.get("baseMaxSize") or 1e10),
                            "stepSize": float(item.get("baseIncrement") or 0.000001)
                        }
                    except Exception as e:
                        print(f"[WARN] 忽略异常交易对 {item.get('symbol')}: {e}")
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
                currency = acc["currency"]
                acc_type = acc.get("type", "")
                available = acc.get("available") or acc.get("balance") or 0
                balance = float(available)
                print(f"[DEBUG] type={acc_type}, currency={currency}, available={available}")
                if balance > 0:
                    balances[currency] = balances.get(currency, 0) + balance
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
        if CONFIG.get("DRY_RUN", False):
            print(f"[DRY_RUN] Would {side.upper()} {symbol} size={size} price={price if price else 'market'}")
            return {"side": side, "symbol": symbol, "size": size, "price": price, "dry_run": True}
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
                body_dict["funds"] = str(size)
            else:
                body_dict["size"] = str(size)
        else:
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
        if "-" not in symbol and symbol not in ["USDT", "USDC", "USDD", "DAI", "BTC", "ETH"]:
            query_symbol = f"{symbol}-USDT"
        else:
            query_symbol = symbol
        url = f"{self.base_url}/api/v1/market/orderbook/level1"
        params = {"symbol": query_symbol}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data and data.get("data") and data["data"].get("price"):
                return float(data["data"]["price"])
            else:
                print(f"[WARN] 无法获取 {query_symbol} 最新价，API返回：{data}")
                return None
        except Exception as e:
            print(f"[ERROR] 获取价格失败 {symbol}: {e}")
            return None