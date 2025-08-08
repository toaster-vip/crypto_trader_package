import pytest
import os
import json
from unittest.mock import patch, MagicMock
from kucoin_api import KuCoinClient, safe_float, to_symbol_pair

@pytest.fixture
def kucoin_client():
    with patch.dict(os.environ, {
        "KUCOIN_API_KEY": "test_key",
        "KUCOIN_API_SECRET": "test_secret",
        "KUCOIN_API_PASSPHRASE": "test_pass"
    }):
        client = KuCoinClient()
        return client

def test_safe_float_valid():
    assert safe_float("123.45") == 123.45

def test_safe_float_invalid():
    assert safe_float(None) == 0.0
    assert safe_float("abc", 1.23) == 1.23

def test_to_symbol_pair():
    assert to_symbol_pair("btc") == "BTC-USDT"
    assert to_symbol_pair("BTC-USDT") == "BTC-USDT"

@patch("kucoin_api.requests.get")
def test_get_symbol_price(mock_get, kucoin_client):
    mock_get.return_value.json.return_value = {
        "data": {"price": "123.45"}
    }
    mock_get.return_value.status_code = 200
    price = kucoin_client.get_symbol_price("BTC-USDT")
    assert price == 123.45

@patch("kucoin_api.requests.get")
def test_get_all_tickers(mock_get, kucoin_client):
    mock_get.return_value.json.return_value = {
        "data": {
            "ticker": [
                {"symbol": "BTC-USDT", "changeRate": "0.1", "volValue": "1000000", "last": "27000"},
                {"symbol": "ETH-USDT", "changeRate": "0.05", "volValue": "500000", "last": "1700"}
            ]
        }
    }
    tickers = kucoin_client.get_all_tickers()
    assert "BTC-USDT" in tickers
    assert tickers["ETH-USDT"]["last"] == 1700.0

@patch("kucoin_api.requests.get")
def test_get_all_prices(mock_get, kucoin_client):
    mock_get.return_value.json.return_value = {
        "data": {
            "ticker": [
                {"symbol": "BTC-USDT", "last": "27500"},
                {"symbol": "ETH-USDT", "last": "1800"}
            ]
        }
    }
    prices = kucoin_client.get_all_prices()
    assert prices["BTC-USDT"] == 27500.0

@patch("kucoin_api.requests.get")
def test_get_klines(mock_get, kucoin_client):
    mock_get.return_value.json.return_value = {
        "data": [
            ["1691500800", "100", "105", "110", "95", "1000", "100000"],
            ["1691587200", "105", "108", "112", "102", "1200", "125000"]
        ]
    }
    df = kucoin_client.get_klines("BTC-USDT", "1hour", 2)
    assert df is not None
    assert "open" in df.columns
    assert df.iloc[-1]["close"] == 108.0

@patch("kucoin_api.requests.get")
def test_get_balances_real(mock_get, kucoin_client):
    kucoin_client.simulate = False
    mock_get.return_value.json.return_value = {
        "data": [
            {"currency": "USDT", "type": "trade", "balance": "123.45"},
            {"currency": "BTC", "type": "trade", "balance": "0.01"}
        ]
    }
    balances = kucoin_client.get_balances()
    assert balances["USDT"] == 123.45
    assert balances["BTC"] == 0.01

def test_get_balances_simulated(kucoin_client):
    kucoin_client.simulate = True
    balances = kucoin_client.get_balances()
    assert balances["USDT"] == 120  # default simulate value

@patch("kucoin_api.requests.post")
def test_place_order_market_buy(mock_post, kucoin_client):
    mock_post.return_value.json.return_value = {
        "code": "200000",
        "data": {"orderId": "1234567890"}
    }
    kucoin_client.simulate = False
    order_id = kucoin_client.place_order("buy", "BTC-USDT", 100)
    assert order_id == "1234567890"

@patch("kucoin_api.requests.get")
def test_get_fills(mock_get, kucoin_client):
    mock_get.return_value.json.return_value = {
        "code": "200000",
        "data": {
            "items": [
                {"size": "0.001", "price": "30000"},
                {"size": "0.002", "price": "31000"}
            ]
        }
    }
    fills = kucoin_client.get_fills("BTC-USDT")
    assert len(fills) == 2