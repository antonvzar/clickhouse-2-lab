CREATE DATABASE IF NOT EXISTS ecom;

USE ecom;

CREATE TABLE IF NOT EXISTS ecom_offers
(
    snapshot_date Date DEFAULT today(),        -- дата снимка каталога
    offer_id      UInt64,
    price         Float64,
    seller_id     UInt64,
    category_id   UInt32,
    vendor        String
)
ENGINE = ReplacingMergeTree(snapshot_date)
PARTITION BY toYYYYMM(snapshot_date)
ORDER BY (category_id, offer_id);

CREATE TABLE IF NOT EXISTS raw_events
(
    Hour            DateTime,
    DeviceTypeName  LowCardinality(String),
    ApplicationName LowCardinality(String),
    OSName          LowCardinality(String),
    ProvinceName    LowCardinality(String),
    ContentUnitID   UInt64
)
ENGINE = MergeTree
PARTITION BY toDate(Hour)
ORDER BY (Hour, ContentUnitID);

-- Каталог товаров
INSERT INTO ecom_offers (offer_id, price, seller_id, category_id, vendor)
SELECT
    offer_id,
    price,
    seller_id,
    category_id,
    vendor
FROM file('/data/EcomOffer.parquet', 'Parquet');

-- Сырые события
INSERT INTO raw_events (Hour, DeviceTypeName, ApplicationName, OSName, ProvinceName, ContentUnitID)
SELECT
    Hour,
    DeviceTypeName,
    ApplicationName,
    OSName,
    ProvinceName,
    ContentUnitID
FROM file('/data/RawEvent.parquet', 'Parquet');

CREATE MATERIALIZED VIEW IF NOT EXISTS catalog_by_category_mv
ENGINE = SummingMergeTree
PARTITION BY category_id
ORDER BY category_id
AS
SELECT
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY category_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS catalog_by_brand_mv
ENGINE = SummingMergeTree
PARTITION BY vendor
ORDER BY (vendor, category_id)
AS
SELECT
    vendor,
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY vendor, category_id;

CREATE MATERIALIZED VIEW IF NOT EXISTS offer_events_mv
ENGINE = SummingMergeTree
PARTITION BY toDate(Hour)
ORDER BY (offer_id)
AS
SELECT
    toDate(r.Hour) AS event_date,
    e.offer_id     AS offer_id,
    e.category_id  AS category_id,
    e.vendor       AS vendor,
    count()        AS events_cnt
FROM raw_events AS r
INNER JOIN ecom_offers AS e
    ON r.ContentUnitID = e.offer_id
GROUP BY event_date, offer_id, category_id, vendor;

SELECT
    category_id,
    offers_cnt
FROM catalog_by_category_mv
ORDER BY offers_cnt DESC
LIMIT 20;

SELECT
    category_id,
    count() AS offers_cnt
FROM ecom_offers
GROUP BY category_id
ORDER BY offers_cnt DESC
LIMIT 20;

SELECT
    vendor,
    sum(offers_cnt) AS offers_cnt
FROM catalog_by_brand_mv
GROUP BY vendor
ORDER BY offers_cnt DESC
LIMIT 30;

SELECT
    category_id,
    avg(offers_cnt) AS avg_offers_per_brand
FROM
(
    SELECT
        category_id,
        vendor,
        count() AS offers_cnt
    FROM ecom_offers
    GROUP BY category_id, vendor
)
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;

SELECT
    category_id,
    avg(offers_cnt) AS avg_offers_per_brand
FROM catalog_by_brand_mv
GROUP BY category_id
ORDER BY avg_offers_per_brand DESC;

SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price
FROM ecom_offers AS o
LEFT JOIN
(
    SELECT DISTINCT ContentUnitID AS offer_id
    FROM raw_events
) AS e USING (offer_id)
WHERE e.offer_id IS NULL;

SELECT
    o.offer_id,
    o.category_id,
    o.vendor,
    o.price
FROM ecom_offers AS o
LEFT JOIN
(
    SELECT DISTINCT offer_id
    FROM offer_events_mv
) AS ev USING (offer_id)
WHERE ev.offer_id IS NULL;
