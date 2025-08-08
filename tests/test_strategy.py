# tests/test_strategy.py

import pytest
import pandas as pd
from strategy import get_top_gainers_and_volume, get_klines, get_symbol_score

# ✅ 模拟API类
class MockAPI:
    def get_all_tickers(self):
        return {
            "AAA-USDT": {"changeRate": "0.15", "volValue": "100000"},
            "BBB-USDT": {"changeRate": "0.10", "volValue": "50000"},
            "CCC-USDT": {"changeRate": "-0.05", "volValue": "200000"},
            "DDD-USDT": {"changeRate": "0.20", "volValue": "1000"},  # 高涨幅低成交量
            "EEE-USDT": {"changeRate": "0.01", "volValue": "10"},    # 弱币
            "ZZZ-BTC": {"changeRate": "0.99", "volValue": "99999"},  # 非USDT对
        }

    def get_klines(self, symbol, interval, limit):
        if symbol == "AAA-USDT":
            # 构造符合要求的K线DataFrame
            rows = []
            for i in range(100):
                rows.append([
                    str(i),                # t
                    "1.0", "1.2",          # open, close
                    "1.3", "0.9",          # high, low
                    "1000", "10000"        # volume, turnover
                ])
            df = pd.DataFrame(rows, columns=["t", "o", "c", "h", "l", "v", "turnover"])
            return df
        return None


@pytest.fixture
def mock_api():
    return MockAPI()


def test_get_top_gainers_and_volume(mock_api):
    result = get_top_gainers_and_volume(mock_api, top_n=3)
    assert isinstance(result, list)
    assert "AAA-USDT" in result
    assert "BBB-USDT" in result
    assert "CCC-USDT" in result
    assert "EEE-USDT" not in result  # 弱币过滤
    assert all(s.endswith("USDT") for s in result)


def test_get_klines_success(mock_api):
    df = get_klines(mock_api, "AAA-USDT", interval="1hour", limit=100)
    assert df is not None
    assert "open" in df.columns
    assert len(df) == 100


def test_get_klines_fail(mock_api):
    df = get_klines(mock_api, "NONEXISTENT-USDT")
    assert df is None


def test_get_symbol_score(mock_api):
    score = get_symbol_score(mock_api, "AAA-USDT")
    assert isinstance(score, dict)
    assert "score" in score
    assert "turnover" in score
    assert "open" in score
    assert "is_new_coin" in score
    assert score["is_new_coin"] is False