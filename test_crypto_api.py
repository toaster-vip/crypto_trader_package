import requests
import json
import time
import hmac
import hashlib

class CryptoComExchangeClient:
    def __init__(self, api_key, api_secret):
        self.api_key = api_key
        self.api_secret = api_secret
        self.base_url = "https://api.crypto.com/v2"

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

    def get_account_summary(self):
        method = "private/get-account-summary"
        req = {
            "id": int(time.time() * 100),
            "method": method,
            "api_key": self.api_key,
            "params": {},
            "nonce": int(time.time() * 1000)
        }

        signed_req = self.sign_request(req)

        try:
            response = requests.post(
                f"{self.base_url}/{method}",
                json=signed_req,
                headers={'Content-Type': 'application/json'}
            )
            response.raise_for_status()
        except requests.exceptions.RequestException as e:
            print(f"❌ 请求失败: {e}")
            if e.response is not None:
                print(f"错误响应: {e.response.text}")
            return None

        return response.json()

# ======== 实际运行测试 ========
if __name__ == "__main__":
    # 请用你的真实 API_KEY 和 API_SECRET 替换以下内容
    API_KEY = "WpWVkahrWSCaJfcmvcJgSv"
    API_SECRET = "cxakp_FDRiZ8aw9UPogTVTgzzJGv"

    client = CryptoComExchangeClient(api_key=API_KEY, api_secret=API_SECRET)
    result = client.get_account_summary()

    if result:
        print("✅ 成功获取账户信息：")
        print(json.dumps(result, indent=4, ensure_ascii=False))
    else:
        print("⚠️ 获取失败")