-- name: null_or_duplicate_order_id
SELECT order_id, COUNT(*) AS n
FROM staging.orders
GROUP BY order_id
HAVING order_id IS NULL OR COUNT(*) > 1;

-- name: delivered_before_purchase
SELECT order_id
FROM staging.orders
WHERE delivered_ts IS NOT NULL AND delivered_ts < purchase_ts;

-- name: payment_not_equal_items_plus_freight
WITH i AS (
    SELECT order_id, SUM(price + freight_value) AS items_total
    FROM staging.order_items GROUP BY order_id
), p AS (
    SELECT order_id, SUM(payment_value) AS paid_total
    FROM staging.order_payments GROUP BY order_id
)
SELECT o.order_id, i.items_total, p.paid_total
FROM staging.orders o
         JOIN i ON i.order_id = o.order_id
         JOIN p ON p.order_id = o.order_id
WHERE ABS(i.items_total - p.paid_total) > 0.01
  AND NOT o.payment_mismatch_flag;

-- name: orders_without_customer
SELECT o.order_id
FROM staging.orders o
         LEFT JOIN staging.customers c ON c.customer_id = o.customer_id
WHERE c.customer_id IS NULL;

-- name: orders_with_multiple_reviews
SELECT order_id, COUNT(*) AS n_reviews
FROM staging.order_reviews
GROUP BY order_id
HAVING COUNT(*) > 1;

-- name: delivered_status_but_no_delivery_date
SELECT order_id
FROM staging.orders
WHERE order_status = 'delivered'
  AND delivered_ts IS NULL
  AND NOT missing_delivery_date_flag;