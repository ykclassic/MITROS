update market_data_providers
set provider_version = 'v2-advanced-public'
where provider_key = 'coinbase';

update market_data_provider_routes
set authority_conditions = '{"on":"failover","cross_validate_with":["kraken"],"four_hour_source":"deterministic_1h_aggregation"}'
where provider_id = (
    select id from market_data_providers where provider_key = 'coinbase'
);
