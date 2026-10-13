CREATE SCHEMA IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.orders;
CREATE TABLE staging.orders AS
SELECT
    NULLIF(TRIM(order_id), '')               AS order_id,
    NULLIF(TRIM(customer_id), '')            AS customer_id,
    LOWER(TRIM(order_status))                AS order_status,
    order_purchase_timestamp::timestamp      AS purchase_ts,
    order_approved_at::timestamp             AS approved_ts,
    order_delivered_carrier_date::timestamp  AS carrier_ts,
    order_delivered_customer_date::timestamp AS delivered_ts,
    order_estimated_delivery_date::timestamp AS estimated_ts,
    FALSE AS missing_delivery_date_flag,
    FALSE AS payment_mismatch_flag
FROM raw.orders;

DROP TABLE IF EXISTS staging.customers;
CREATE TABLE staging.customers AS
SELECT
    NULLIF(TRIM(customer_id), '')        AS customer_id,
    NULLIF(TRIM(customer_unique_id), '') AS customer_unique_id,
    customer_zip_code_prefix             AS customer_zip_prefix,
    customer_city,
    UPPER(TRIM(customer_state))          AS customer_state
FROM raw.customers;

DROP TABLE IF EXISTS staging.order_items;
CREATE TABLE staging.order_items AS
SELECT
    TRIM(order_id)                 AS order_id,
    order_item_id::int             AS order_item_id,
    TRIM(product_id)               AS product_id,
    TRIM(seller_id)                AS seller_id,
    shipping_limit_date::timestamp AS shipping_limit_ts,
    price::numeric(12,2)           AS price,
    freight_value::numeric(12,2)   AS freight_value
FROM raw.order_items;

DROP TABLE IF EXISTS staging.order_payments;
CREATE TABLE staging.order_payments AS
SELECT
    TRIM(order_id)                 AS order_id,
    payment_sequential::int        AS payment_sequential,
    payment_type,
    payment_installments::int      AS payment_installments,
    payment_value::numeric(12,2)   AS payment_value
FROM raw.order_payments;

DROP TABLE IF EXISTS staging.order_reviews;
CREATE TABLE staging.order_reviews AS
SELECT
    TRIM(review_id)                    AS review_id,
    TRIM(order_id)                     AS order_id,
    review_score::int                  AS review_score,
    review_creation_date::timestamp    AS review_creation_ts,
    review_answer_timestamp::timestamp AS review_answer_ts
FROM raw.order_reviews;

DROP TABLE IF EXISTS staging.products;
CREATE TABLE staging.products AS
SELECT
    TRIM(product_id) AS product_id,
    COALESCE(NULLIF(TRIM(product_category_name), ''), 'unknown') AS product_category_name
FROM raw.products;

DROP TABLE IF EXISTS staging.sellers;
CREATE TABLE staging.sellers AS
SELECT TRIM(seller_id) AS seller_id, seller_city, UPPER(TRIM(seller_state)) AS seller_state
FROM raw.sellers;