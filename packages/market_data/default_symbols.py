DEFAULT_SYMBOL_MAPPINGS: dict[str, dict[str, str]] = {
    "twelvedata": {
        "BTC/USD": "BTC/USD",
        "ETH/USD": "ETH/USD",
        "SOL/USD": "SOL/USD",
    },
    "finnhub": {
        "BTC/USD": "BINANCE:BTCUSDT",
        "ETH/USD": "BINANCE:ETHUSDT",
        "SOL/USD": "BINANCE:SOLUSDT",
    },
    "alphavantage": {
        "BTC/USD": "BTC",
        "ETH/USD": "ETH",
        "SOL/USD": "SOL",
    },
    "coinbase": {
        "BTC/USD": "BTC-USD",
        "ETH/USD": "ETH-USD",
        "SOL/USD": "SOL-USD",
        "BTC/USDT": "BTC-USDT",
        "ETH/USDT": "ETH-USDT",
        "SOL/USDT": "SOL-USDT",
    },
    "kraken": {
        "BTC/USD": "BTC/USD",
        "ETH/USD": "ETH/USD",
        "SOL/USD": "SOL/USD",
        "BTC/USDT": "XBTUSDT",
        "ETH/USDT": "ETHUSDT",
        "SOL/USDT": "SOLUSDT",
    },
    "coingecko": {
        "BTC/USD": "bitcoin",
        "ETH/USD": "ethereum",
        "SOL/USD": "solana",
    },
}
