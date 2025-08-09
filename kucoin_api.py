# kucoin_api.py
import requests
import time
import hmac
import base64
import hashlib
import json
import urllib.parse
from typing import Optional, Dict, Any
from config import CONFIG


def safe_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def to_symbol_pair(symbol: str) -> str:
    s = (symbol or "").upper()
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
        self.symbol_limits_cache: Dict[str, Dict[str, float]] = {}
        print("🔑 [KuCoinClient] 使用 KuCoin API KEY:", (self.api_key[:5] + "***") if self.api_key else "(未配置)")
        print("📁 [KuCoinClient] config.py 加载成功")
        self._init_symbol_limits_cache()

    # ===== 签名：必须把 querystring 拼进 requestPath =====
    def _get_headers(
        self,
        method: str,
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        body: Optional[Any] = None,
    ) -> Dict[str, str]:
        """
        KuCoin V2:
        prehash = timestamp + method + requestPath + body
        requestPath = endpoint + ('?' + urlencode(params_sorted))  (若有 params)
        body 为字符串（POST json 且无需空格）
        """
        ts = str(int(time.time() * 1000))

        # querystring 必须按 key 排序并 URL 编码
        request_path = endpoint
        if params:
            sorted_items = sorted(params.items(), key=lambda kv: kv[0])
            query = urllib.parse.urlencode(sorted_items, doseq=True)
            request_path = f"{endpoint}?{query}"

        if body is None:
            body_str = ""
        elif isinstance(body, (dict, list)):
            body_str = json.dumps(body, separators=(",", ":"), ensure_ascii=False)
        else:
            body_str = str(body)

        prehash = f"{ts}{method.upper()}{request_path}{body_str}"

        signature = base64.b64encode(
            hmac.new(self.api_secret.encode("utf-8"), prehash.encode("utf-8"), hashlib.sha256).digest()
        ).decode()
        passphrase = base64.b64encode(
            hmac.new(self.api_secret.encode("utf-8"), self.passphrase.encode("utf-8"), hashlib.sha256).digest()
        ).decode()

        return {
            "KC-API-KEY": self.api_key,
            "KC-API-SIGN": signature,
            "KC-API-TIMESTAMP": ts,
            "KC-API-PASSPHRASE": passphrase,
            "KC-API-KEY-VERSION": "2",
            "Content-Type": "application/json",
        }

    # ===== 公共：交易对限制缓存 =====
    def _init_symbol_limits_cache(self):
        print("[INFO] ⏳ 正在加载所有交易对限制信息...")
        try:
            url = self.base_url + "/api/v1/symbols"
            response = requests.get(url, timeout=10)
            data = response.json()
            for item in data.get("data", []):
                if item.get("enableTrading"):
                    try:
                        self.symbol_limits_cache[item["symbol"]] = {
                            "minFunds": safe_float(item.get("minFunds")),
                            "minSize": safe_float(item.get("baseMinSize")),
                            "maxSize": safe_float(item.get("baseMaxSize"), 1e10),
                            "stepSize": safe_float(item.get("baseIncrement"), 0.000001),
                        }
                    except Exception as e:
                        print(f"[WARN] 忽略异常交易对 {item.get('symbol')}: {e}")
            print(f"[INFO] ✅ 已缓存 {len(self.symbol_limits_cache)} 个交易对限制参数")
        except Exception as e:
            print(f"[ERROR] 初始化 symbol 限制缓存失败: {e}")

    def get_symbol_limits(self, symbol: str):
        return self.symbol_limits_cache.get(to_symbol_pair(symbol))

    # ===== 公共行情 =====
    def get_all_tickers(self) -> Dict[str, Dict[str, float]]:
        url = self.base_url + "/api/v1/market/allTickers"
        for _ in range(3):
            try:
                resp = requests.get(url, timeout=10)
                data = resp.json()
                tickers = {}
                print("🔥 using safe_float for all tickers!")
                for t in data.get("data", {}).get("ticker", []):
                    tickers[t["symbol"]] = {
                        "changeRate": safe_float(t.get("changeRate")),
                        "volValue": safe_float(t.get("volValue")),
                        "last": safe_float(t.get("last")),
                    }
                return tickers
            except Exception as e:
                print(f"[ERROR] 获取全市场ticker失败: {e}")
                time.sleep(2)
        return {}

    def get_all_prices(self) -> Dict[str, float]:
        tickers = self.get_all_tickers()
        return {k: v["last"] for k, v in tickers.items()}

    def get_market_data(self, symbol: str) -> Dict[str, float]:
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
            print(f"[ERROR] 获取行情失败 {symbol}: {e}")
            return {}

    def get_symbol_price(self, symbol: str) -> Optional[float]:
        sym = to_symbol_pair(symbol)
        url = f"{self.base_url}/api/v1/market/orderbook/level1"
        params = {"symbol": sym}
        try:
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            px = (data or {}).get("data", {}).get("price")
            if px is not None:
                return safe_float(px)
            print(f"[WARN] 无法获取 {sym} 最新价，API返回：{data}")
            return None
        except Exception as e:
            print(f"[ERROR] 获取价格失败 {symbol}: {e}")
            return None

    def get_klines(self, symbol: str, interval: str = "1hour", limit: int = 100):
        url = self.base_url + "/api/v1/market/candles"
        params = {"symbol": to_symbol_pair(symbol), "type": interval}
        for _ in range(3):
            try:
                resp = requests.get(url, params=params, timeout=10)
                data = resp.json()
                candles = data.get("data", [])
                if not candles or not isinstance(candles, list):
                    print(f"[ERROR] K线数据为空: {symbol}")
                    return None
                import pandas as pd
                df = pd.DataFrame(candles, columns=["t", "o", "c", "h", "l", "v", "turnover"])
                df = df.sort_values(by="t")
                for col in ["o", "c", "h", "l", "v", "turnover"]:
                    df[col] = df[col].map(safe_float)
                df["open"] = df["o"]
                df["close"] = df["c"]
                df["high"] = df["h"]
                df["low"] = df["l"]
                df["volume"] = df["v"]
                return df
            except Exception as e:
                print(f"[ERROR] K线获取失败 {symbol}: {e}")
                time.sleep(2)
        return None

    # ===== 私有：账户与持仓 =====
    def get_account_holdings(self) -> Dict[str, float]:
        endpoint = "/api/v1/accounts"
        headers = self._get_headers("GET", endpoint, params=None, body=None)
        try:
            response = requests.get(self.base_url + endpoint, headers=headers, timeout=10)
            data = response.json()
            balances = {}
            for acc in data.get("data", []):
                currency = acc.get("currency")
                available = acc.get("available") or acc.get("balance") or 0
                balance = safe_float(available)
                if currency and balance > 0:
                    balances[currency] = balances.get(currency, 0.0) + balance
            return balances
        except Exception as e:
            print(f"[ERROR] 获取账户持仓失败: {e}")
            return {}

    def get_balances(self, simulate: Optional[bool] = None) -> Dict[str, float]:
        sim = self.simulate if simulate is None else simulate
        if sim:
            return {"USDT": CONFIG.get("SIM_START_BALANCE", 1000)}
        return self.get_account_holdings()

    def get_positions(self, simulate: Optional[bool] = None) -> Dict[str, Dict[str, float]]:
        sim = self.simulate if simulate is None else simulate
        if sim:
            return {}
        balances = self.get_account_holdings()
        positions = {}
        for coin, amount in balances.items():
            if coin not in ["USDT", "USD", "USDC", "DAI"] and amount > 0:
                positions[f"{coin}-USDT"] = {"amount": amount}
        return positions

    # ===== 私有：下单与成交 =====
    def place_order(self, side: str, symbol: str, size: float, price: Optional[float] = None):
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
            "type": order_type,
        }
        if order_type == "market":
            if side == "buy":
                body_dict["funds"] = str(size)   # 买：按 USDT 金额
            else:
                body_dict["size"] = str(size)    # 卖：按币数量
        else:
            body_dict["size"] = str(size)
            body_dict["price"] = str(price)

        body = json.dumps(body_dict, separators=(",", ":"), ensure_ascii=False)
        headers = self._get_headers("POST", endpoint, params=None, body=body)
        try:
            response = requests.post(url, headers=headers, data=body, timeout=10)
            result = response.json()
            if result.get("code") == "200000":
                order_id = result["data"]["orderId"]
                print(f"[✅] 下单成功（{side} {symbol_pair}）: {order_id}")
                return order_id
            print(f"[ERROR] 下单失败: {result}")
            return None
        except Exception as e:
            print(f"[ERROR] 下单请求异常: {e}")
            return None

    def get_fills(self, symbol: str, side: Optional[str] = None, limit: int = 50):
        endpoint = "/api/v1/fills"
        params = {
            "symbol": to_symbol_pair(symbol),
            "tradeType": "TRADE",
            "pageSize": limit,
        }
        if side:
            params["side"] = side
        headers = self._get_headers("GET", endpoint, params=params, body=None)
        try:
            response = requests.get(self.base_url + endpoint, headers=headers, params=params, timeout=10)
            data = response.json()
            if data.get("code") == "200000":
                return data.get("data", {}).get("items", [])
            print(f"[get_fills] 失败: {data}")
            return []
        except Exception as e:
            print(f"[get_fills] 异常: {e}")
            return []

    def get_supported_symbols(self):
        return list(self.symbol_limits_cache.keys())