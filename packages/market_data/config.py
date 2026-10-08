from pydantic_settings import BaseSettings, SettingsConfigDict


class MarketDataSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MITROS_MARKET_")

    freshness_seconds: int = 120
    cross_validation_tolerance: str = "0.01"
    twelvedata_api_key: str | None = None
    finnhub_api_key: str | None = None
    alphavantage_api_key: str | None = None
    coingecko_api_key: str | None = None
