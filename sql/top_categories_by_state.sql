-- Q2: Top 3 product categories per customer state by revenue
WITH category_revenue AS (
    SELECT c.customer_state,
           COALESCE(p.product_category_name, 'unknown') AS category,
           SUM(i.price) AS revenue
    FROM staging.order_items i
             JOIN staging.orders o     ON o.order_id = i.order_id
             JOIN staging.customers c  ON c.customer_id = o.customer_id
             LEFT JOIN staging.products p ON p.product_id = i.product_id
    WHERE o.order_status = 'delivered'
    GROUP BY 1, 2
), ranked AS (
    SELECT *, DENSE_RANK() OVER (PARTITION BY customer_state ORDER BY revenue DESC) AS rnk
    FROM category_revenue
)
SELECT customer_state, rnk, category, ROUND(revenue, 2) AS revenue
FROM ranked
WHERE rnk <= 3
ORDER BY customer_state, rnk;