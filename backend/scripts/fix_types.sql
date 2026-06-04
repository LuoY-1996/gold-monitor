-- 修复 PostgreSQL 表列类型：TEXT → DATE / DOUBLE PRECISION
-- 运行方式: psql "postgresql://..." -f fix_types.sql

ALTER TABLE gold_prices_au9999 ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE gold_prices_au9999 ALTER COLUMN open TYPE DOUBLE PRECISION USING open::double precision;
ALTER TABLE gold_prices_au9999 ALTER COLUMN high TYPE DOUBLE PRECISION USING high::double precision;
ALTER TABLE gold_prices_au9999 ALTER COLUMN low TYPE DOUBLE PRECISION USING low::double precision;
ALTER TABLE gold_prices_au9999 ALTER COLUMN close TYPE DOUBLE PRECISION USING close::double precision;

ALTER TABLE gold_prices_xau_usd ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE gold_prices_xau_usd ALTER COLUMN open TYPE DOUBLE PRECISION USING open::double precision;
ALTER TABLE gold_prices_xau_usd ALTER COLUMN high TYPE DOUBLE PRECISION USING high::double precision;
ALTER TABLE gold_prices_xau_usd ALTER COLUMN low TYPE DOUBLE PRECISION USING low::double precision;
ALTER TABLE gold_prices_xau_usd ALTER COLUMN close TYPE DOUBLE PRECISION USING close::double precision;

ALTER TABLE factor_usd_cny ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE factor_usd_cny ALTER COLUMN close TYPE DOUBLE PRECISION USING close::double precision;

ALTER TABLE factor_vix ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE factor_vix ALTER COLUMN close TYPE DOUBLE PRECISION USING close::double precision;

ALTER TABLE factor_treasury_10y ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE factor_treasury_10y ALTER COLUMN yield_value TYPE DOUBLE PRECISION USING yield_value::double precision;

ALTER TABLE factor_oil ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE factor_oil ALTER COLUMN close TYPE DOUBLE PRECISION USING close::double precision;

ALTER TABLE factor_fed_funds ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE factor_fed_funds ALTER COLUMN rate TYPE DOUBLE PRECISION USING rate::double precision;

ALTER TABLE geopolitical_events ALTER COLUMN event_date TYPE DATE USING event_date::date;

ALTER TABLE geopolitical_risk_index ALTER COLUMN trade_date TYPE DATE USING trade_date::date;
ALTER TABLE geopolitical_risk_index ALTER COLUMN risk_score TYPE DOUBLE PRECISION USING risk_score::double precision;
ALTER TABLE geopolitical_risk_index ALTER COLUMN event_intensity TYPE DOUBLE PRECISION USING event_intensity::double precision;

-- 设置序列
SELECT setval('gold_prices_au9999_id_seq', (SELECT COALESCE(MAX(id), 1) FROM gold_prices_au9999));
SELECT setval('factor_usd_cny_id_seq', (SELECT COALESCE(MAX(id), 1) FROM factor_usd_cny));
SELECT setval('factor_vix_id_seq', (SELECT COALESCE(MAX(id), 1) FROM factor_vix));

\echo 'Done!'
