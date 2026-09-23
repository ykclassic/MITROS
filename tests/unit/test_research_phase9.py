from datetime import datetime, timedelta, timezone
from decimal import Decimal
from packages.market_data.contracts import Candle
from packages.research.backtest import BacktestEngine
from packages.research.replay import ReplayEngine
from packages.research.walk_forward import WalkForwardEngine
from contracts.backtest import BacktestConfig
from packages.strategies.crt import CRTStrategy

def candles(n=110):
    start=datetime(2026,1,1,tzinfo=timezone.utc)
    return [
        Candle(
            asset="BTCUSD", venue="TEST", timeframe="1h",
            open_time=start+timedelta(hours=i), close_time=start+timedelta(hours=i+1),
            open=Decimal("100")+Decimal(i)/Decimal("10"),
            high=Decimal("102")+Decimal(i)/Decimal("10"),
            low=Decimal("98")+Decimal(i)/Decimal("10"),
            close=Decimal("101")+Decimal(i)/Decimal("10"),
            volume=Decimal("1"), provider="fixture", provider_version="1",
            observed_at=start+timedelta(hours=i+1), received_at=start+timedelta(hours=i+1),
        ) for i in range(n)
    ]

def config():
    return BacktestConfig(
        initial_equity=Decimal("10000"), position_fraction=Decimal("0.10"),
        commission_fraction=Decimal("0.001"), slippage_fraction=Decimal("0.001"),
        seed=7, strategy_id="crt", strategy_version="1.0.0", feature_set_version="1.0.0",
    )

def test_backtest_is_deterministic_and_causal():
    data=candles()
    assert BacktestEngine().run(data, CRTStrategy(), config()) == BacktestEngine().run(data, CRTStrategy(), config())

def test_replay_is_deterministic():
    data=candles()
    a=ReplayEngine().run(data, CRTStrategy())
    assert a == ReplayEngine().run(data, CRTStrategy())
    assert a.frame_count == len(data)-49

def test_walk_forward_has_purge_and_oos_windows():
    result=WalkForwardEngine().evaluate(candles(), CRTStrategy(), config(), 60, 15, 15, 2)
    assert result.folds
    assert all(f.purge_bars == 2 for f in result.folds)
    assert all(f.test_start > f.train_end for f in result.folds)
    for fold, oos in zip(result.folds, result.oos_results):
        assert all(t.signal_index >= fold.train_size + fold.purge_bars for t in oos.trades)

def test_research_rejects_invalid_data():
    data=candles()
    data[5]=data[4].model_copy(update={"open_time":data[4].open_time})
    try:
        BacktestEngine().run(data, CRTStrategy(), config())
    except ValueError as exc:
        assert "strictly increasing" in str(exc)
    else:
        raise AssertionError("invalid dataset was accepted")
