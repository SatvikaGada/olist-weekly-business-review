# Olist Weekly Business Review

An ELT pipeline, data-quality checks, SQL analysis and a satisfaction study for the Olist Brazilian e-commerce dataset (about 100k orders, 2016 to 2018). It loads the raw CSVs into PostgreSQL, builds cleaned staging tables and a one-row-per-order mart, stops with an alarm if any data-quality check fails, answers five business questions in SQL, and produces the charts and metrics behind a memo to a Vice President.

## Prerequisites

- Python 3.10 or newer
- PostgreSQL 14 or newer (running on localhost, port 5432)
- Git

## Setup

```powershell
git clone https://github.com/<your-username>/olist-weekly-business-review.git
cd olist-weekly-business-review
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Data

Download the dataset from https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce and extract the CSV files into a folder named `data/` in the project root. The pipeline needs these eight files: orders, order_items, order_payments, order_reviews, customers, sellers, products and geolocation. The category translation file is not used.

## Database

Create the database once (UTF-8, so Portuguese characters load correctly):

```powershell
psql -U postgres -c "CREATE DATABASE olist ENCODING 'UTF8' TEMPLATE template0 LC_COLLATE 'C' LC_CTYPE 'C';"
```

Then set the password for this terminal session. The password is read from an environment variable and is never stored in the code.

```powershell
$env:PG_PASSWORD = "your_postgres_password"
```

Optional variables, with defaults: `PG_USER` (postgres), `PG_HOST` (localhost), `PG_PORT` (5432), `PG_DB` (olist).

## Run

```powershell
python src/pipeline.py
python src/analysis.py
```

`pipeline.py` validates the source files, loads the raw tables, builds the staging tables, runs the six data-quality checks, applies the handling rules, re-checks, and builds the mart. It writes a log to `pipeline.log` and the check results to `reports/dq_results.csv`.

`analysis.py` runs the five Part C queries, saves each result to `reports/query_results/`, computes the metric values, and saves four charts to `reports/charts/`. Run it only after `pipeline.py` has succeeded.

## Project layout

- `src/pipeline.py`: the ELT pipeline with logging, source validation and the data-quality alarm
- `src/analysis.py`: runs the Part C queries, computes metrics and draws the charts
- `sql/staging.sql`, `sql/mart.sql`: build the cleaned staging tables and the analysis-ready mart
- `sql/data_quality.sql`: the six data-quality checks (Part B)
- `sql/dq_handling.sql`: how each failing check is handled (dropped, fixed or flagged)
- `sql/monthly_revenue.sql`, `sql/top_categories_by_state.sql`, `sql/rolling_average_orders.sql`, `sql/repeat_purchase_rate.sql`, `sql/delivery_delay_reviews.sql`: the five Part C queries, one per file
- `reports/`: generated results, charts and the final PDF report

## Design notes

**Idempotent.** Each raw table is dropped, recreated and loaded inside a single transaction, and the staging and mart tables are dropped and rebuilt on every run. Running the pipeline twice gives identical row counts and never duplicates data.

**Failure handling.** Every step is logged. Before loading, the pipeline checks that every expected file and column exists and reports all problems in one clear message. A database connection failure or a missing `PG_PASSWORD` also stops the run with a readable error.

**Data-quality alarm.** The six checks run before and after the handling rules. If any check still returns failing rows after handling, the pipeline raises an error and the mart is not built. Rows that are deliberately flagged rather than removed (payment mismatches and missing delivery dates) are excluded from the alarm query because they already carry a flag column in staging.

**No double-counting.** Items, payments and reviews are each reduced to one row per order before they are joined, and the pipeline verifies that the mart has exactly one row per order.

**Customer identity.** `customer_id` is regenerated for every order in Olist, so it cannot identify a returning customer. Repeat-purchase analysis uses `customer_unique_id`.

**Revenue definition.** Revenue is the sum of item prices on delivered orders. `delivery_delay_days` is positive when an order arrives after the estimated date and negative when it arrives early.

## Data-quality results

| Check | Failing rows | Handling |
|---|---|---|
| Null or duplicate order_id | 0 | Drop nulls, keep one row per order_id |
| Delivered date before purchase date | 0 | Set delivery date to NULL |
| Payment total not equal to items + freight | 303 | Flagged, rows kept |
| Orders with no matching customer | 0 | Dropped |
| More than one review per order | 547 | Kept the latest review |
| Delivered status but no delivery date | 8 | Flagged, excluded from delay metrics |

## Key findings

- Revenue peaked at BRL 987,765 in November 2017 and held between BRL 826k and 978k through 2018.
- Only 3.0% of customers (2,801 of 93,358) ordered more than once.
- Late delivery is the main driver of low reviews: orders that arrive early average 4.29 stars, while orders 8 or more days late average 1.70 stars.

The full analysis and the memo to the Vice President are in the PDF report in `reports/`.