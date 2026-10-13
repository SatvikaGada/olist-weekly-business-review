-- 1. null / duplicate order_id: drop nulls, keep one row per order_id
DELETE FROM staging.orders WHERE order_id IS NULL;
DELETE FROM staging.orders a USING staging.orders b
WHERE a.order_id = b.order_id AND a.ctid > b.ctid;

-- 2. delivered before purchase: timestamp is impossible, so set to NULL
UPDATE staging.orders SET delivered_ts = NULL
WHERE delivered_ts IS NOT NULL AND delivered_ts < purchase_ts;

-- 3. payment <> items + freight: flag, keep the row
UPDATE staging.orders o SET payment_mismatch_flag = TRUE
    FROM (
    SELECT i.order_id
    FROM (SELECT order_id, SUM(price + freight_value) AS t
          FROM staging.order_items GROUP BY order_id) i
    JOIN (SELECT order_id, SUM(payment_value) AS t
          FROM staging.order_payments GROUP BY order_id) p
      ON p.order_id = i.order_id
    WHERE ABS(i.t - p.t) > 0.01
) m
WHERE o.order_id = m.order_id;

-- 4. orders without a customer: drop, they cannot be attributed
DELETE FROM staging.orders o
WHERE NOT EXISTS (SELECT 1 FROM staging.customers c WHERE c.customer_id = o.customer_id);

-- 5. several reviews per order: keep the latest
DELETE FROM staging.order_reviews r
    USING (
    SELECT ctid AS rid,
           ROW_NUMBER() OVER (PARTITION BY order_id
                              ORDER BY review_answer_ts DESC NULLS LAST,
                                       review_creation_ts DESC NULLS LAST,
                                       review_id) AS rn
    FROM staging.order_reviews
) d
WHERE r.ctid = d.rid AND d.rn > 1;

-- 6. delivered but no delivery date: flag, exclude from delay metrics
UPDATE staging.orders SET missing_delivery_date_flag = TRUE
WHERE order_status = 'delivered' AND delivered_ts IS NULL;