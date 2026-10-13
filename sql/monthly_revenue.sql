-- Q1: Month-over-month revenue and growth percentage
WITH monthly AS (
    SELECT DATE_TRUNC('month', purchase_ts)::date AS month,
    SUM(items_price) AS revenue
FROM mart.order_summary
WHERE order_status = 'delivered'
GROUP BY 1
    )
SELECT month,
    ROUND(revenue, 2) AS revenue,
    ROUND(LAG(revenue) OVER (ORDER BY month), 2) AS prev_month_revenue,
    ROUND(100.0 * (revenue - LAG(revenue) OVER (ORDER BY month))
    / NULLIF(LAG(revenue) OVER (ORDER BY month), 0), 2) AS mom_growth_pct
FROM monthly
ORDER BY month;