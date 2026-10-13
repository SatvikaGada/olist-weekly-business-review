-- Q4: Repeat-purchase rate.
-- customer_id is regenerated for EVERY order in Olist, so it cannot identify a returning
-- customer. customer_unique_id is the real person identifier.
WITH per_customer AS (
    SELECT customer_unique_id, COUNT(DISTINCT order_id) AS orders
    FROM mart.order_summary
    WHERE order_status = 'delivered'
    GROUP BY customer_unique_id
)
SELECT COUNT(*) AS customers,
       COUNT(*) FILTER (WHERE orders >= 2) AS repeat_customers,
    ROUND(100.0 * COUNT(*) FILTER (WHERE orders >= 2) / COUNT(*), 2) AS repeat_rate_pct
FROM per_customer;