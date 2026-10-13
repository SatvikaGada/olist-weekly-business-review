-- Q3: 7-day rolling average of daily order count (missing days filled with 0)
WITH daily AS (
    SELECT purchase_date AS day, COUNT(*) AS orders
FROM mart.order_summary
GROUP BY 1
    ), calendar AS (
SELECT d::date AS day
FROM generate_series((SELECT MIN(day) FROM daily),
    (SELECT MAX(day) FROM daily), INTERVAL '1 day') AS d
    ), filled AS (
SELECT c.day, COALESCE(d.orders, 0) AS orders
FROM calendar c LEFT JOIN daily d ON d.day = c.day
    )
SELECT day, orders,
    ROUND(AVG(orders) OVER (ORDER BY day ROWS BETWEEN 6 PRECEDING AND CURRENT ROW), 2)
    AS rolling_7d_avg
FROM filled
ORDER BY day;