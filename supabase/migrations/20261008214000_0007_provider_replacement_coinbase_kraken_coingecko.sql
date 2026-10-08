update market_data_provider_routes
set active = false
where provider_id in (
    select id from market_data_providers
    where provider_key in ('twelvedata', 'finnhub', 'alphavantage')
);

update market_data_providers
set active = false
where provider_key in ('twelvedata', 'finnhub', 'alphavantage');

insert into market_data_providers(
    provider_key, provider_version, priority, role, supported_timeframes,
    supported_venues, cross_validate, authority_conditions, active
)
values
    ('kraken','v1-spot-rest',1,'PRIMARY',array['15m','1h','4h'],array['spot'],true,
     '{"on":"request","fallback_on":["unavailable","invalid","stale","incomplete","conflicted"]}',true),
    ('coinbase','v1-exchange-rest',2,'SECONDARY',array['15m','1h','4h'],array['spot'],true,
     '{"on":"failover","cross_validate_with":["coingecko"]}',true),
    ('coingecko','v1-market-chart-hourly',3,'EMERGENCY',array['1h','4h'],array['spot'],false,
     '{"on":"emergency","independent_validation":true}',true)
on conflict (provider_key) do update set
    provider_version=excluded.provider_version,
    priority=excluded.priority,
    role=excluded.role,
    supported_timeframes=excluded.supported_timeframes,
    supported_venues=excluded.supported_venues,
    authority_conditions=excluded.authority_conditions,
    active=true;

insert into market_data_symbol_mappings(provider_id, canonical_asset, provider_symbol)
select p.id, m.canonical_asset, m.provider_symbol
from market_data_providers p
join (
    values
        ('kraken','BTC/USD','BTC/USD'),('kraken','ETH/USD','ETH/USD'),('kraken','SOL/USD','SOL/USD'),
        ('coinbase','BTC/USD','BTC-USD'),('coinbase','ETH/USD','ETH-USD'),('coinbase','SOL/USD','SOL-USD'),
        ('coingecko','BTC/USD','bitcoin'),('coingecko','ETH/USD','ethereum'),('coingecko','SOL/USD','solana')
) as m(provider_key, canonical_asset, provider_symbol)
on m.provider_key=p.provider_key
on conflict (provider_id, canonical_asset) do update set
    provider_symbol=excluded.provider_symbol, active=true;

insert into market_data_provider_routes(
    provider_id, role, priority, cross_validate, supported_timeframes,
    supported_venues, authority_conditions, active
)
select id, role, priority, cross_validate, supported_timeframes,
       supported_venues, authority_conditions, true
from market_data_providers
where provider_key in ('kraken','coinbase','coingecko')
on conflict (provider_id) do update set
    role=excluded.role, priority=excluded.priority, cross_validate=excluded.cross_validate,
    supported_timeframes=excluded.supported_timeframes, supported_venues=excluded.supported_venues,
    authority_conditions=excluded.authority_conditions, active=true;

update market_data_symbol_mappings
set active=false
where provider_id in (
    select id from market_data_providers
    where provider_key in ('twelvedata','finnhub','alphavantage')
);
