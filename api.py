# api.py
import time
import hmac
import hashlib
import requests
import json

from config import API_KEY, API_SECRET, BASE_URL


class CryptoComExchangeClient:
    def __init__(self, api_key, api_secret, base_url=BASE_URL):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = base_url

    def sign_request(self, req):
        param_string = ""
        if "params" in req:
            for key in sorted(req['params']):
                param_string += key
                param_string += str(req['params'][key])
        sig_payload = req['method'] + str(req['id']) + self.api_key + param_string + str(req['nonce'])
        req['sig'] = hmac.new(
            bytes(self.api_secret, 'utf-8'),
            msg=bytes(sig_payload, 'utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()
        return req

    def send_request(self, method, params=None):
        req = {
            "id": int(time.time() * 1000),
            "method": method,
            "api_key": self.api_key,
            "params": params or {},
            "nonce": int(time.time() * 1000)
        }
        signed = self.sign_request(req)
        try:
            resp = requests.post(f"{self.base_url}/{method}", json=signed)
            resp.raise_for_status()
            data = resp.json()
            if data.get("code") != 0:
                print(f"[ERROR] 接口返回错误: {data}")
                return None
            return data.get("result")
        except Exception as e:
            print(f"[EXCEPTION] 请求失败: {e}")
            return None

    def get_account_summary(self):
        return self.send_request("private/get-account-summary")

    def get_open_orders(self, symbol):
        return self.send_request("private/get-open-orders", {"instrument_name": symbol})

    def create_order(self, symbol, side, price, quantity):
        """
        下单（真实）
        """
        params = {
            "instrument_name": symbol,
            "side": side.upper(),  # BUY or SELL
            "type": "LIMIT",
            "price": str(price),
            "quantity": str(quantity),
            "client_oid": f"oid_{int(time.time() * 1000)}"
        }
        return self.send_request("private/create-order", params)

    def cancel_order(self, order_id):
        return self.send_request("private/cancel-order", {"order_id": order_id})

    def get_symbol_price(self, symbol):
        try:
            resp = requests.get(f"{self.base_url}/public/get-ticker", params={"instrument_name": symbol})
            resp.raise_for_status()
            data = resp.json()
            return float(data["result"]["data"]["a"])  # 最新买一价
        except Exception as e:
            print(f"[ERROR] 获取 {symbol} 价格失败: {e}")
            return None

    def get_all_instruments(self):
        try:
            resp = requests.get(f"{self.base_url}/public/get-instruments")
            resp.raise_for_status()
            return resp.json().get("result", {}).get("instruments", [])
        except Exception as e:
            print(f"[ERROR] 获取交易对失败: {e}")
            return []
        
    def get_valid_symbols(self):
        """
        获取支持的交易对（App API 不支持 /get-instruments 时使用 fallback）
        """
        try:
            response = requests.get(f"{self.base_url}/public/get-instruments")
            response.raise_for_status()
            data = response.json()
            return [item["instrument_name"] for item in data["result"]["instruments"]]
        except Exception as e:
            print(f"[WARN] 获取交易对失败，使用默认硬编码 SYMBOLS")
            return [
                "BOME_USDT", "SHIB_USDT", "TRUMP_USDT",
                "DOGE_USDT", "BTC_USDT", "ETH_USDT", "CRO_USDT"
            ] 

    def get_account_holdings(self):
        result = self.get_account_summary()
        if not result:
            return []
        accounts = result.get("accounts", [])
        return [
            {"symbol": acc["currency"], "balance": float(acc["balance"])}
            for acc in accounts
            if float(acc.get("balance", 0)) > 0
        ]


# 初始化客户端对象供其他模块调用
client = CryptoComExchangeClient(API_KEY, API_SECRET)

def get_symbol_price(symbol):
    return client.get_symbol_price(symbol)

def get_account_holdings():
    return client.get_account_holdings()

def get_valid_symbols():
    return client.get_valid_symbols()

def place_order(symbol, side, price, quantity):
    return client.create_order(symbol, side, price, quantity)