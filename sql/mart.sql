CREATE SCHEMA IF NOT EXISTS mart;

DROP TABLE IF EXISTS mart.order_summary;
CREATE TABLE mart.order_summary AS
WITH items AS (
    SELECT order_id, COUNT(*) AS item_count,
           SUM(price) AS items_price, SUM(freight_value) AS freight_total
    FROM staging.order_items GROUP BY order_id
), pay AS (
    SELECT order_id, SUM(payment_value) AS payment_total
    FROM staging.order_payments GROUP BY order_id
)
SELECT
    o.order_id, o.customer_id, c.customer_unique_id, c.customer_state,
    o.order_status, o.purchase_ts, DATE(o.purchase_ts) AS purchase_date,
    o.delivered_ts, o.estimated_ts,
    COALESCE(i.item_count, 0)  AS item_count,
    i.items_price, i.freight_total,
    i.items_price + i.freight_total AS items_plus_freight,
    p.payment_total,
    CASE WHEN o.delivered_ts IS NOT NULL
    THEN o.delivered_ts::date - o.estimated_ts::date END AS delivery_delay_days,
    r.review_score,
    o.payment_mismatch_flag, o.missing_delivery_date_flag
FROM staging.orders o
JOIN staging.customers c        ON c.customer_id = o.customer_id
LEFT JOIN items i               ON i.order_id = o.order_id
LEFT JOIN pay p                 ON p.order_id = o.order_id
LEFT JOIN staging.order_reviews r ON r.order_id = o.order_id;