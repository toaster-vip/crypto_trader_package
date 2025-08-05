# kucoin_api.py
import requests
import time
import os
from config import CONFIG
from log_utils import log_error, log_debug, log_info

# 官方SDK需先装 pip install kucoin-python
try:
    from kucoin.client import Client as KCClient
except ImportError:
    KCClient = None

def to_symbol_pair(symbol):
    # 自动转化为标准对：如 BTC-USDT
    symbol = symbol.upper()
    if "-" in symbol:
        return symbol
    if not symbol.endswith("USDT"):
        return f"{symbol}-USDT"
    return symbol

class KuCoinClient:
    def __init__(self):
        self.base_url = "https://api.kucoin.com"
        self.api_key = CONFIG["KUCOIN_API_KEY"]
        self.api_secret = CONFIG["KUCOIN_API_SECRET"]
        self.api_passphrase = CONFIG["KUCOIN_API_PASSPHRASE"]
        self.simulate = CONFIG.get("DRY_RUN", False) or CONFIG.get("SIMULATE", False)
        self._kc = None
        if not self.simulate and KCClient and self.api_key:
            self._kc = KCClient(self.api_key, self.api_secret, self.api_passphrase)

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
        tickers = self.get_all_tickers()
        return {k: v["last"] for k, v in tickers.items()}

    ### --- K线数据 ---
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

    ### --- 账户资产 ---
    def get_balances(self, simulate=False):
        if self.simulate or simulate:
            return {"USDT": CONFIG.get("SIM_START_BALANCE", 1000)}
        if not self._kc:
            log_error("未配置KuCoin实盘API，无法查资产")
            return {}
        try:
            balances = self._kc.get_accounts()
            usdt = next((float(a['available']) for a in balances if a['currency'] == 'USDT' and a['type']=='trade'), 0)
            return {"USDT": usdt}
        except Exception as e:
            log_error(f"实盘查资产异常: {e}")
            return {}

    ### --- 当前持仓（简易化，按虚拟盘设计，实盘建议扩展到实际持币）---
    def get_positions(self, simulate=False):
        if self.simulate or simulate:
            return {}  # 虚拟盘可自定义模拟持仓结构
        log_info("实盘暂不支持多币明细持仓查询（如需请开发币种资产明细接口）")
        return {}

    ### --- 下单接口 ---
    def place_order(self, side, symbol, amount):
        symbol_pair = to_symbol_pair(symbol)
        if self.simulate:
            log_info(f"[模拟下单] {side.upper()} {symbol_pair} 数量: {amount}")
            return
        if not self._kc:
            log_error("未配置KuCoin实盘API，无法实盘下单")
            return
        try:
            # KuCoin仅支持买入时指定资金base/quote
            side_api = "buy" if side.lower() == "buy" else "sell"
            if side_api == "buy":
                # 按资金额买入，市价
                order = self._kc.create_market_order(symbol_pair, side_api, size=None, funds=str(amount))
            else:
                # 卖出建议加 size，需查持仓（如需实盘请实现实际持仓管理）
                order = self._kc.create_market_order(symbol_pair, side_api, size=str(amount))
            log_info(f"[实盘下单] {side.upper()} {symbol_pair} 成功: {order}")
            return order
        except Exception as e:
            log_error(f"实盘下单失败: {side} {symbol_pair} {amount}, 错误: {e}")

    ### --- 单币实时价格 ---
    def get_symbol_price(self, symbol):
        prices = self.get_all_prices()
        pair = to_symbol_pair(symbol)
        return prices.get(pair, None)