-- Q5: Delivery delay vs estimate, and its relationship with review score
WITH base AS (
    SELECT delivery_delay_days, review_score,
           CASE WHEN delivery_delay_days < 0               THEN '1. Early'
                WHEN delivery_delay_days = 0               THEN '2. On estimated day'
                WHEN delivery_delay_days BETWEEN 1 AND 3   THEN '3. 1-3 days late'
                WHEN delivery_delay_days BETWEEN 4 AND 7   THEN '4. 4-7 days late'
                ELSE '5. 8+ days late' END AS delay_bucket
    FROM mart.order_summary
    WHERE order_status = 'delivered'
      AND delivery_delay_days IS NOT NULL
      AND review_score IS NOT NULL
)
SELECT COALESCE(delay_bucket, 'ALL DELIVERED ORDERS') AS delay_bucket,
       COUNT(*) AS orders,
       ROUND(AVG(delivery_delay_days), 2) AS avg_delay_days,
       ROUND(AVG(review_score), 2) AS avg_review_score,
       ROUND(100.0 * AVG((review_score <= 2)::int), 1) AS pct_1_2_star
FROM base
GROUP BY ROLLUP (delay_bucket)
ORDER BY GROUPING(delay_bucket), delay_bucket;