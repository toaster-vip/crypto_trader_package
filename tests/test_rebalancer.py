import pytest
import tempfile
import json
from decimal import Decimal
from unittest.mock import MagicMock, patch
from rebalancer import (
    load_entry_price_state, save_entry_price_state,
    load_cooldown_pool, save_cooldown_pool,
    get_dynamic_entry_price, rebalance_portfolio
)

# ---------- Fixture ----------
@pytest.fixture
def mock_api():
    api = MagicMock()
    api.get_fills.return_value = [
        {"price": "1.0", "size": "10"},
        {"price": "2.0", "size": "5"}
    ]
    api.get_symbol_price.return_value = 1.5
    api.get_all_prices.return_value = {"ABC-USDT": 1.5}
    api.get_symbol_limits.return_value = {"minFunds": 5.0}
    api.get_balances.return_value = {"USDT": 100}
    api.get_positions.return_value = {}
    return api

# ---------- Test Entry Price State ----------
def test_entry_price_state_load_save(tmp_path):
    file = tmp_path / "entry.json"
    state = {"ABC-USDT": 1.23}
    with patch("rebalancer.ENTRY_PRICE_FILE", file):
        save_entry_price_state(state)
        loaded = load_entry_price_state()
        assert loaded == state

# ---------- Test Cooldown Pool ----------
def test_cooldown_pool_load_save(tmp_path):
    file = tmp_path / "cooldown.json"
    pool = {"ABC-USDT": 123}
    with patch("rebalancer.COOLDOWN_FILE", file):
        save_cooldown_pool(pool)
        loaded = load_cooldown_pool()
        assert loaded == pool

# ---------- Test get_dynamic_entry_price ----------
def test_get_dynamic_entry_price_from_local():
    symbol = "ABC-USDT"
    entry_price_state = {symbol: 1.23}
    pos = {}
    result = get_dynamic_entry_price(symbol, pos, entry_price_state)
    assert result == Decimal("1.23")

def test_get_dynamic_entry_price_from_api(mock_api):
    symbol = "ABC-USDT"
    entry_price_state = {}
    pos = {}
    result = get_dynamic_entry_price(symbol, pos, entry_price_state, api=mock_api)
    assert result == Decimal("1.33")  # weighted avg of (10*1 + 5*2) / 15 = 1.333...

def test_get_dynamic_entry_price_all_missing():
    symbol = "ABC-USDT"
    entry_price_state = {}
    pos = {}
    result = get_dynamic_entry_price(symbol, pos, entry_price_state)
    assert result == Decimal("0")

# ---------- Test rebalance_portfolio ----------
def test_rebalance_portfolio_buy_only(mock_api):
    cooldown = {}
    entry_price_state = {}
    top_symbols = ["ABC-USDT"]

    def fake_place_order(side, symbol, size, price=None):
        assert side == "buy"
        assert symbol == "ABC-USDT"
        return "ORDER123"

    with patch("rebalancer.load_entry_price_state", return_value=entry_price_state), \
         patch("rebalancer.save_entry_price_state"), \
         patch("rebalancer.save_cooldown_pool"), \
         patch("rebalancer.print_snapshot"), \
         patch("rebalancer.print_cooldown_pool"), \
         patch("rebalancer.log_info"), \
         patch("rebalancer.log_trade_detail"):
        rebalance_portfolio(
            top_symbols,
            balances=mock_api.get_balances(),
            positions=mock_api.get_positions(),
            place_order=fake_place_order,
            price_map=mock_api.get_all_prices(),
            dry_run=False,
            api=mock_api,
            cooldown_pool=cooldown,
            current_round=10,
            cooldown_rounds=3
        )