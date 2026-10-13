"""Runs the Part C queries, prints/saves results, computes metric values, draws 4 charts.
Run:  python src/analysis.py   (after pipeline.py succeeded)
"""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

from pipeline import get_engine, SQL_DIR, REPORT_DIR

OUT = REPORT_DIR / "query_results"
CHARTS = REPORT_DIR / "charts"
OUT.mkdir(parents=True, exist_ok=True)
CHARTS.mkdir(parents=True, exist_ok=True)

QUERIES = {
    "q1_monthly_revenue": "monthly_revenue.sql",
    "q2_top_categories_by_state": "top_categories_by_state.sql",
    "q3_rolling_orders": "rolling_average_orders.sql",
    "q4_repeat_rate": "repeat_purchase_rate.sql",
    "q5_delay_vs_review": "delivery_delay_reviews.sql",
}

METRICS_SQL = """
SELECT
  ROUND(100.0 * AVG((review_score >= 4)::int)
        FILTER (WHERE order_status = 'delivered' AND review_score IS NOT NULL), 2)
        AS satisfied_order_rate_pct,
  ROUND(100.0 * AVG((delivery_delay_days <= 0)::int)
        FILTER (WHERE order_status = 'delivered' AND delivery_delay_days IS NOT NULL), 2)
        AS on_time_delivery_rate_pct,
  ROUND(100.0 * AVG((order_status = 'canceled')::int), 2) AS cancellation_rate_pct
FROM mart.order_summary
"""

MONTHLY_SQL = """
SELECT DATE_TRUNC('month', purchase_ts)::date AS month,
       ROUND(100.0 * AVG((delivery_delay_days <= 0)::int), 2) AS on_time_pct,
       ROUND(AVG(review_score), 2) AS avg_review
FROM mart.order_summary
WHERE order_status = 'delivered' AND delivery_delay_days IS NOT NULL
GROUP BY 1 ORDER BY 1
"""


def main():
    engine = get_engine()
    res = {}
    with engine.connect() as conn:
        for name, fname in QUERIES.items():
            df = pd.read_sql_query((SQL_DIR / fname).read_text(encoding="utf-8"), conn)
            df.to_csv(OUT / f"{name}.csv", index=False)
            res[name] = df
            print(f"\n=== {name} ({fname}) ===")
            print(df.head(12).to_string(index=False))
        metrics = pd.read_sql_query(METRICS_SQL, conn)
        monthly = pd.read_sql_query(MONTHLY_SQL, conn)
    print("\n=== metric values ===")
    print(metrics.to_string(index=False))
    metrics.to_csv(OUT / "metric_values.csv", index=False)

    window = lambda d, col: d[(d[col] >= "2017-01-01") & (d[col] <= "2018-08-31")]

    # Chart 1: monthly revenue
    q1 = res["q1_monthly_revenue"].copy()
    q1["month"] = pd.to_datetime(q1["month"])
    q1 = window(q1, "month")
    plt.figure(figsize=(8, 4))
    plt.plot(q1["month"], q1["revenue"], marker="o")
    plt.title("Monthly revenue of delivered orders (Jan 2017 - Aug 2018)")
    plt.xlabel("Month"); plt.ylabel("Revenue (BRL, item prices)")
    plt.grid(alpha=.3); plt.tight_layout()
    plt.savefig(CHARTS / "chart1_monthly_revenue.png", dpi=150); plt.close()

    # Chart 2: daily orders + 7-day rolling average
    q3 = res["q3_rolling_orders"].copy()
    q3["day"] = pd.to_datetime(q3["day"])
    q3 = window(q3, "day")
    plt.figure(figsize=(8, 4))
    plt.plot(q3["day"], q3["orders"], alpha=.3, label="Daily orders")
    plt.plot(q3["day"], q3["rolling_7d_avg"], linewidth=2, label="7-day rolling average")
    plt.title("Daily order volume with 7-day rolling average")
    plt.xlabel("Date"); plt.ylabel("Orders per day")
    plt.legend(); plt.grid(alpha=.3); plt.tight_layout()
    plt.savefig(CHARTS / "chart2_rolling_orders.png", dpi=150); plt.close()

    # Chart 3: review score by delay bucket
    q5 = res["q5_delay_vs_review"]
    q5 = q5[q5["delay_bucket"] != "ALL DELIVERED ORDERS"]
    plt.figure(figsize=(8, 4))
    plt.bar(q5["delay_bucket"], q5["avg_review_score"], color="tab:blue")
    plt.title("Average review score by delivery delay vs estimate")
    plt.xlabel("Delivery vs estimated date"); plt.ylabel("Average review score (1-5)")
    plt.ylim(1, 5); plt.xticks(rotation=15, ha="right"); plt.tight_layout()
    plt.savefig(CHARTS / "chart3_review_by_delay.png", dpi=150); plt.close()

    # Chart 4: monthly on-time rate vs average review
    monthly["month"] = pd.to_datetime(monthly["month"])
    monthly = window(monthly, "month")
    fig, ax1 = plt.subplots(figsize=(8, 4))
    ax1.bar(monthly["month"], monthly["on_time_pct"], width=20, alpha=.4,
            label="On-time delivery rate (%)")
    ax1.set_xlabel("Purchase month"); ax1.set_ylabel("On-time delivery rate (%)")
    ax2 = ax1.twinx()
    ax2.plot(monthly["month"], monthly["avg_review"], color="tab:red", marker="o",
             label="Average review score")
    ax2.set_ylabel("Average review score (1-5)")
    plt.title("Monthly on-time delivery rate vs average review score")
    fig.tight_layout()
    plt.savefig(CHARTS / "chart4_ontime_vs_review.png", dpi=150); plt.close()
    print("\nCharts saved in", CHARTS)


if __name__ == "__main__":
    main()