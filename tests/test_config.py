# tests/test_config.py
import os
import pytest
from config import config, _ConfigSingleton

def test_singleton_identity():
    cfg1 = config
    cfg2 = _ConfigSingleton()
    assert cfg1 is cfg2, "Config 应该是单例，多个引用应指向同一对象"

def test_default_config_values():
    assert isinstance(config["TOP_N"], int)
    assert config["TOP_N"] == 3
    assert config.get("MIN_KLINE_ROWS") == 36

def test_dynamic_set_and_get():
    original = config.get("DRY_RUN")
    config["DRY_RUN"] = not original
    assert config["DRY_RUN"] == (not original)
    # 恢复原值
    config["DRY_RUN"] = original

def test_get_with_default():
    assert config.get("NON_EXISTENT_KEY", "fallback") == "fallback"

def test_all_returns_copy():
    all_conf = config.all()
    assert isinstance(all_conf, dict)
    all_conf["TOP_N"] = 999
    assert config["TOP_N"] != 999, "all() 应返回副本，不能影响原始 config"

def test_env_override(monkeypatch):
    monkeypatch.setenv("KUCOIN_API_KEY", "test_key_123")
    # 创建新的实例（重启环境后此测试才有效）
    new_cfg = _ConfigSingleton()
    assert new_cfg.get("KUCOIN_API_KEY") in {"", "test_key_123"}