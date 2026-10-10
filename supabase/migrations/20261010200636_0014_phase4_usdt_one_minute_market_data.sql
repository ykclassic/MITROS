-- Enable current one-minute price evidence for the Phase 4 risk gate.
-- Keep the quote currency explicit: USDT candles must not be relabelled USD candles.
update public.market_data_provider_routes r
set supported_timeframes = (
    select array_agg(distinct timeframe order by timeframe)
    from unnest(r.supported_timeframes || array['1m']::text[]) as timeframe
)
from public.market_data_providers p
where p.id = r.provider_id
  and p.provider_key in ('kraken', 'coinbase')
  and r.active = true;

insert into public.market_data_symbol_mappings
    (provider_id, canonical_asset, provider_symbol, active)
select p.id, mapping.canonical_asset, mapping.provider_symbol, true
from public.market_data_providers p
join (
    values
        ('kraken', 'BTC/USDT', 'XBTUSDT'),
        ('kraken', 'ETH/USDT', 'ETHUSDT'),
        ('kraken', 'SOL/USDT', 'SOLUSDT'),
        ('coinbase', 'BTC/USDT', 'BTC-USDT'),
        ('coinbase', 'ETH/USDT', 'ETH-USDT'),
        ('coinbase', 'SOL/USDT', 'SOL-USDT')
) as mapping(provider_key, canonical_asset, provider_symbol)
  on mapping.provider_key = p.provider_key
on conflict (provider_id, canonical_asset)
do update set provider_symbol = excluded.provider_symbol, active = true;
