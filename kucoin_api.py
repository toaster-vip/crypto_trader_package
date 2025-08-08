import os
import time
import hmac
import base64
import hashlib
import json
import requests
import pandas as pd
from config import CONFIG
from log_utils import log_info, log_error, log_debug

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
        self.simulate = CONFIG.get("DRY_RUN", False) or CONFIG.get("SIMULATE", False)
        self.symbol_limits_cache = {}

        log_info(f"[KuCoinClient] 使用 API KEY: {self.api_key[:5]}***")
        self._init_symbol_limits_cache()

    def _get_headers(self, method, endpoint, body=""):
        now = str(int(time.time() * 1000))
        body = body or ""
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
        try:
            url = self.base_url + "/api/v1/symbols"
            resp = requests.get(url, timeout=10)
            data = resp.json()
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
                        log_debug(f"[限额跳过] {item.get('symbol')}: {e}")
            log_info(f"[限额缓存] 已缓存 {len(self.symbol_limits_cache)} 个交易对")
        except Exception as e:
            log_error(f"[限额加载失败] {e}")

    def get_symbol_limits(self, symbol):
        return self.symbol_limits_cache.get(to_symbol_pair(symbol))

    def get_all_tickers(self):
        url = self.base_url + "/api/v1/market/allTickers"
        for _ in range(3):
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
                log_error(f"[Ticker获取失败] {e}")
                time.sleep(2)
        return {}

    def get_all_prices(self):
        tickers = self.get_all_tickers()
        return {k: v["last"] for k, v in tickers.items()}

    def get_market_data(self, symbol):
        url = self.base_url + f"/api/v1/market/stats?symbol={to_symbol_pair(symbol)}"
        try:
            response = requests.get(url, timeout=10)
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
            log_error(f"[行情失败] {symbol}: {e}")
            return {}

    def get_symbol_price(self, symbol):
        sym = to_symbol_pair(symbol)
        url = f"{self.base_url}/api/v1/market/orderbook/level1"
        try:
            response = requests.get(url, params={"symbol": sym}, timeout=10)
            response.raise_for_status()
            data = response.json()
            return safe_float(data.get("data", {}).get("price"))
        except Exception as e:
            log_error(f"[价格失败] {symbol}: {e}")
            return None

    def get_klines(self, symbol, interval="1hour", limit=100):
        url = self.base_url + "/api/v1/market/candles"
        params = {"symbol": to_symbol_pair(symbol), "type": interval}
        for _ in range(3):
            try:
                resp = requests.get(url, params=params, timeout=10)
                df = pd.DataFrame(resp.json().get("data", []), columns=[
                    't', 'o', 'c', 'h', 'l', 'v', 'turnover'])
                df = df.sort_values(by='t')
                for col in ['o', 'c', 'h', 'l', 'v', 'turnover']:
                    df[col] = df[col].map(safe_float)
                df.rename(columns={
                    'o': 'open', 'c': 'close', 'h': 'high',
                    'l': 'low', 'v': 'volume'
                }, inplace=True)
                return df
            except Exception as e:
                log_error(f"[K线失败] {symbol}: {e}")
                time.sleep(2)
        return None

    def get_account_holdings(self):
        endpoint = "/api/v1/accounts"
        headers = self._get_headers("GET", endpoint)
        try:
            resp = requests.get(self.base_url + endpoint, headers=headers, timeout=10)
            data = resp.json()
            balances = {}
            for acc in data.get("data", []):
                cur = acc["currency"]
                balance = safe_float(acc.get("available") or acc.get("balance"))
                if balance > 0:
                    balances[cur] = balances.get(cur, 0) + balance
            return balances
        except Exception as e:
            log_error(f"[账户获取失败] {e}")
            return {}

    def get_balances(self, simulate=None):
        return {"USDT": CONFIG["SIM_START_BALANCE"]} if (simulate or self.simulate) else self.get_account_holdings()

    def get_positions(self, simulate=None):
        if simulate or self.simulate:
            return {}
        balances = self.get_account_holdings()
        return {
            f"{coin}-USDT": {"amount": amt}
            for coin, amt in balances.items()
            if coin not in {"USDT", "USD", "DAI", "USDC"} and amt > 0
        }

    def place_order(self, side, symbol, size, price=None):
        symbol = to_symbol_pair(symbol)
        if CONFIG.get("DRY_RUN"):
            log_info(f"[DRY_RUN] Would {side.upper()} {symbol} size={size} price={price or 'market'}")
            return {"dry_run": True, "side": side, "symbol": symbol, "size": size, "price": price}

        url = self.base_url + "/api/v1/orders"
        order_type = "market" if price is None else "limit"
        body = {
            "clientOid": str(int(time.time() * 1000)),
            "side": side,
            "symbol": symbol,
            "type": order_type
        }
        if order_type == "market":
            body["funds" if side == "buy" else "size"] = str(size)
        else:
            body.update({"size": str(size), "price": str(price)})

        headers = self._get_headers("POST", "/api/v1/orders", json.dumps(body))
        try:
            resp = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
            result = resp.json()
            if result.get("code") == "200000":
                log_info(f"[下单成功] {side.upper()} {symbol} → {result['data']['orderId']}")
                return result["data"]["orderId"]
            log_error(f"[下单失败] {result}")
        except Exception as e:
            log_error(f"[下单异常] {e}")
        return None

    def get_fills(self, symbol, side=None, limit=50):
        url = self.base_url + "/api/v1/fills"
        params = {
            "symbol": to_symbol_pair(symbol),
            "tradeType": "TRADE",
            "pageSize": limit
        }
        if side:
            params["side"] = side
        headers = self._get_headers("GET", "/api/v1/fills")
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            if resp.json().get("code") == "200000":
                return resp.json().get("data", {}).get("items", [])
        except Exception as e:
            log_error(f"[成交查询失败] {symbol}: {e}")
        return []

    def get_supported_symbols(self):
        return list(self.symbol_limits_cache.keys())