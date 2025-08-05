# kucoin_api.py
import requests
import time
import os
from config import CONFIG
from log_utils import log_error, log_debug

class KuCoinClient:
    def __init__(self):
        self.base_url = "https://api.kucoin.com"
        self.api_key = os.getenv("KUCOIN_API_KEY", "")  # 推荐用环境变量
        self.api_secret = os.getenv("KUCOIN_API_SECRET", "")
        self.api_passphrase = os.getenv("KUCOIN_API_PASSPHRASE", "")
        # ...如需实盘签名，建议加 kucoin-python sdk

    ### --- 热门榜行情 ---
    def get_all_tickers(self):
        url = self.base_url + "/api/v1/market/allTickers"
        for retry in range(3):
            try:
                resp = requests.get(url, timeout=10)
                data = resp.json()
                tickers = {}
                for t in data.get("data", {}).get("ticker", []):
                    tickers[t['symbol']] = {
                        "changeRate": float(t.get("changeRate", 0)),
                        "volValue": float(t.get("volValue", 0)),
                        "last": float(t.get("last", 0)),
                    }
                return tickers
            except Exception as e:
                log_error(f"获取全市场ticker失败: {e}")
                time.sleep(2)
        return {}

    def get_all_prices(self):
        # 返回 {symbol: last_price}
        tickers = self.get_all_tickers()
        return {k: v["last"] for k, v in tickers.items()}

    ### --- K线数据 ---
    def get_klines(self, symbol, interval="1hour", limit=100):
        # interval: '1min', '5min', '15min', '30min', '1hour', ...
        url = self.base_url + "/api/v1/market/candles"
        params = {"symbol": symbol, "type": interval}
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
                df['open'] = df['o'].astype(float)
                df['close'] = df['c'].astype(float)
                df['high'] = df['h'].astype(float)
                df['low'] = df['l'].astype(float)
                df['volume'] = df['v'].astype(float)
                df['turnover'] = df['turnover'].astype(float)
                return df
            except Exception as e:
                log_error(f"K线获取失败 {symbol}: {e}")
                time.sleep(2)
        return None

    ### --- 账户资产&持仓 ---
    def get_balances(self, simulate=False):
        if simulate or CONFIG.get("DRY_RUN", False):
            return {"USDT": CONFIG.get("SIM_START_BALANCE", 1000)}  # 简单模拟
        # 实盘需用官方SDK或API签名，这里只留占位
        log_error("实盘资产查询未实现，需接入API SDK！")
        return {}

    def get_positions(self, simulate=False):
        if simulate or CONFIG.get("DRY_RUN", False):
            return {}  # 模拟盘没有历史持仓
        log_error("实盘持仓查询未实现，需接入API SDK！")
        return {}

    ### --- 下单接口 ---
    def place_order(self, side, symbol, amount):
        if CONFIG.get("DRY_RUN", False):
            log_debug(f"[模拟下单] {side} {symbol} 数量: {amount}")
            return
        # 实盘需用官方SDK签名提交，留接口
        log_error("实盘下单未实现，需接入官方SDK！")
        return

    ### --- 实盘补充说明 ---
    # 如需实盘，请用 kucoin-python SDK 并补充签名。此处仅为量化/模拟和主行情API落地演示。