import requests
import time
import hmac
import base64
import hashlib
import json
import os
from config import CONFIG
from log_utils import log_error, log_debug, log_info

def safe_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default

def to_symbol_pair(symbol):
    s = symbol.upper()
    if "-" in s:
        return s
    if not s.endswith("USDT"):
        return f"{s}-USDT"
    return s

class KuCoinClient:
    def __init__(self):
        self.api_key = CONFIG["KUCOIN_API_KEY"]
        self.api_secret = CONFIG["KUCOIN_API_SECRET"]
        self.passphrase = CONFIG["KUCOIN_API_PASSPHRASE"]
        self.base_url = "https://api.kucoin.com"
        self.simulate = CONFIG.get("DRY_RUN", False)
        self.symbol_limits_cache = {}
        self._init_symbol_limits_cache()
        if self.api_key:
            print("🔑 [KuCoinClient] 使用 KuCoin API KEY:", self.api_key[:5] + "***")
        print("📁 [KuCoinClient] config.py 加载成功")

    ### 签名 headers
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

    ### 缓存交易对规则
    def _init_symbol_limits_cache(self):
        print("[INFO] ⏳ 正在加载所有交易对限制信息...")
        try:
            url = self.base_url + "/api/v1/symbols"
            response = requests.get(url)
            data = response.json()
            for item in data.get("data", []):
                if item.get("enableTrading"):
                    try:
                        self.symbol_limits_cache[item["symbol"]] = {
                            "minFunds": safe_float(item.get("minFunds")),
                            "minSize": safe_float(item.get("baseMinSize")),
                            "maxSize": safe_float(item.get("baseMaxSize"), 1e10),
                            "stepSize": safe_float(item.get("baseIncrement"), 0.000001)
                        }
                    except Exception as e:
                        print(f"[WARN] 忽略异常交易对 {item.get('symbol')}: {e}")
            print(f"[INFO] ✅ 已缓存 {len(self.symbol_limits_cache)} 个交易对限制参数")
        except Exception as e:
            print(f"[ERROR] 初始化 symbol 限制缓存失败: {e}")

    def get_symbol_limits(self, symbol):
        return self.symbol_limits_cache.get(to_symbol_pair(symbol), None)

    ### 行情榜，所有 ticker
    def get_all_tickers(self):
        url = self.base_url + "/api/v1/market/allTickers"
        for retry in range(3):
            try:
                resp = requests.get(url, timeout=10)
                data = resp.json()
                tickers = {}
                for t in data.get("data", {}).get("ticker", []):
                    tickers[t['symbol']] = {
                        "changeRate": safe_float(t.get("changeRate")),
                        "volValue": safe_float(t.get("volValue")),
                        "last": safe_float(t.get("last")),
                    }
                return tickers
            except Exception as e:
                log_error(f"获取全市场ticker失败: {e}")
                time.sleep(2)
        return {}

    def get_all_prices(self):
        tickers = self.get_all_tickers()
        return {k: v["last"] for k, v in tickers.items()}

    def get_market_data(self, symbol):
        url = self.base_url + f"/api/v1/market/stats?symbol={to_symbol_pair(symbol)}"
        try:
            response = requests.get(url)
            data = response.json()
            ticker = data.get("data", {})
            return {
                "price": safe_float(ticker.get("last")),
                "open": safe_float(ticker.get("open")),
                "high": safe_float(ticker.get("high")),
                "low": safe_float(ticker.get("low")),
                "vol": safe_float(ticker.get("vol")),
            }
        except Exception as e:
            print(f"[ERROR] 获取行情失败 {symbol}: {e}")
            return {}

    def get_symbol_price(self, symbol):
        url = f"{self.base_url}/api/v1/market/orderbook/level1"
        params = {"symbol": to_symbol_pair(symbol)}
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data and data.get("data") and data["data"].get("price"):
                return safe_float(data["data"]["price"])
            else:
                print(f"[WARN] 无法获取 {symbol} 最新价，API返回：{data}")
                return None
        except Exception as e:
            print(f"[ERROR] 获取价格失败 {symbol}: {e}")
            return None

    def get_klines(self, symbol, interval="1hour", limit=100):
        url = self.base_url + "/api/v1/market/candles"
        params = {"symbol": to_symbol_pair(symbol), "type": interval}
        for retry in range(3):
            try:
                resp = requests.get(url, params=params, timeout=10)
                data = resp.json()
                candles = data.get("data", [])
                if not candles or not isinstance(candles, list):
                    log_error(f"K线数据为空: {symbol}")
                    return None
                import pandas as pd
                df = pd.DataFrame(candles, columns=['t','o','c','h','l','v','turnover'])
                df = df.sort_values(by='t')
                for col in ['o', 'c', 'h', 'l', 'v', 'turnover']:
                    df[col] = df[col].map(safe_float)
                df['open'] = df['o']
                df['close'] = df['c']
                df['high'] = df['h']
                df['low'] = df['l']
                df['volume'] = df['v']
                return df
            except Exception as e:
                log_error(f"K线获取失败 {symbol}: {e}")
                time.sleep(2)
        return None

    ### 账户持仓
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
                balance = safe_float(available)
                if balance > 0:
                    balances[currency] = balances.get(currency, 0) + balance
            return balances
        except Exception as e:
            print(f"[ERROR] 获取账户持仓失败: {e}")
            return {}

    def get_balances(self, simulate=False):
        if self.simulate or simulate:
            return {"USDT": CONFIG.get("SIM_START_BALANCE", 1000)}
        return self.get_account_holdings()

    ### 简化虚拟盘持仓
    def get_positions(self, simulate=False):
        if self.simulate or simulate:
            return {}  # 自行维护虚拟盘明细
        print("[INFO] 实盘多币种明细持仓可扩展！默认只查主币。")
        return {}

    ### 下单（实盘签名，buy funds，sell size）
    def place_order(self, side, symbol, size, price=None):
        symbol_pair = to_symbol_pair(symbol)
        if CONFIG.get("DRY_RUN", False):
            print(f"[DRY_RUN] Would {side.upper()} {symbol_pair} size={size} price={price if price else 'market'}")
            return {"side": side, "symbol": symbol_pair, "size": size, "price": price, "dry_run": True}
        endpoint = "/api/v1/orders"
        url = self.base_url + endpoint
        order_type = "market" if price is None else "limit"
        body_dict = {
            "clientOid": str(int(time.time() * 1000)),
            "side": side,
            "symbol": symbol_pair,
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
                print(f"[✅] 下单成功（{side} {symbol_pair}）: {result['data']['orderId']}")
                return result["data"]["orderId"]
            else:
                print(f"[ERROR] 下单失败: {result}")
                return None
        except Exception as e:
            print(f"[ERROR] 下单请求异常: {e}")
            return None

    def get_supported_symbols(self):
        return list(self.symbol_limits_cache.keys())