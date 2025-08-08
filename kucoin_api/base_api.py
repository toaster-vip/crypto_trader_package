import time
import hmac
import base64
import hashlib
import requests
import json
from config import CONFIG
from log_utils import log_error, log_debug

class KuCoinBaseAPI:
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

    def _get(self, endpoint, params=None, signed=False):
        url = self.base_url + endpoint
        headers = self._get_headers("GET", endpoint) if signed else None
        try:
            resp = requests.get(url, headers=headers, params=params, timeout=10)
            return resp.json()
        except Exception as e:
            log_debug(f"[API GET失败] {endpoint}: {e}")
            return None

    def _post(self, endpoint, body_dict=None):
        url = self.base_url + endpoint
        body = json.dumps(body_dict or {})
        headers = self._get_headers("POST", endpoint, body)
        try:
            resp = requests.post(url, headers=headers, data=body, timeout=10)
            return resp.json()
        except Exception as e:
            log_debug(f"[API POST失败] {endpoint}: {e}")
            return None