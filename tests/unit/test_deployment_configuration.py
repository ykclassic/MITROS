from pathlib import Path

import pytest

from packages.market_data.config import MarketDataSettings
from packages.operations.config import ExecutionMode, ProductionConfig


ROOT = Path(__file__).parents[2]


def test_paper_mode_is_the_safe_default() -> None:
    config = ProductionConfig.from_env({})
    assert config.execution_mode is ExecutionMode.PAPER
    assert not config.live_trading_enabled
    assert not config.live_trading_acknowledged


def test_live_mode_requires_explicit_enablement_and_acknowledgement() -> None:
    with pytest.raises(ValueError):
        ProductionConfig.from_env({"MITROS_EXECUTION_MODE": "live"})

    with pytest.raises(ValueError):
        ProductionConfig.from_env(
            {
                "MITROS_EXECUTION_MODE": "live",
                "MITROS_LIVE_TRADING_ENABLED": "true",
            }
        )

    config = ProductionConfig.from_env(
        {
            "MITROS_EXECUTION_MODE": "live",
            "MITROS_LIVE_TRADING_ENABLED": "true",
            "MITROS_LIVE_TRADING_ACK": "I_UNDERSTAND_LIVE_TRADING",
        }
    )
    assert config.execution_mode is ExecutionMode.LIVE
    assert config.live_trading_enabled
    assert config.live_trading_acknowledged


def test_market_provider_keys_use_backend_namespace(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MITROS_MARKET_TWELVEDATA_API_KEY", "td")
    monkeypatch.setenv("MITROS_MARKET_FINNHUB_API_KEY", "fh")
    monkeypatch.setenv("MITROS_MARKET_ALPHAVANTAGE_API_KEY", "av")

    settings = MarketDataSettings()
    assert settings.twelvedata_api_key == "td"
    assert settings.finnhub_api_key == "fh"
    assert settings.alphavantage_api_key == "av"


def test_env_example_contains_no_real_credentials_and_required_boundaries() -> None:
    content = (ROOT / ".env.example").read_text(encoding="utf-8")
    assert "MITROS_MARKET_TWELVEDATA_API_KEY=" in content
    assert "SUPABASE_SERVICE_ROLE_KEY=" in content
    assert "NEXT_PUBLIC" not in content
    assert "I_UNDERSTAND_LIVE_TRADING" not in content
    assert "sk-" not in content


def test_deployment_docs_define_public_private_boundary() -> None:
    content = (ROOT / "docs/architecture/deployment-configuration.md").read_text(
        encoding="utf-8"
    )
    assert "NEXT_PUBLIC_SUPABASE_ANON_KEY" in content
    assert "SUPABASE_SERVICE_ROLE_KEY" in content
    assert "MITROS_MARKET_TWELVEDATA_API_KEY" in content
    assert "MITROS_MT5_PASSWORD" in content
