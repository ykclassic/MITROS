from pydantic_settings import BaseSettings,SettingsConfigDict

class MarketDataSettings(BaseSettings):
    model_config=SettingsConfigDict(env_prefix="MITROS_MARKET_")
    freshness_seconds:int=120
    twelvedata_api_key:str|None=None
    finnhub_api_key:str|None=None
    alphavantage_api_key:str|None=None
