# Dataset contract

## Scope and local location

VerbalVis reads a local copy of the Olist CSV dataset from
`backend/data/olist/`. The dataset is a development and research input; it is
not bundled, fetched, or served by the application. This repository remains a
standalone prototype and is not wired to a dataset distribution service.

## Source and reuse boundary

The canonical public reference is the [Brazilian E-Commerce Public Dataset by
Olist on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).
That page is a source locator, not a statement of licence or redistribution
rights. Contributors must verify the source's applicable reuse and
redistribution terms before publishing, sharing, or redistributing any data
copy.

## Expected source files

`backend/db.py` reads these CSV files:

- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_order_payments_dataset.csv`

## Integrity procedure

After obtaining the CSV files from an approved source, confirm that the local
directory contains the expected files and record their hashes for the release
record:

```powershell
Get-FileHash backend/data/olist/*.csv -Algorithm SHA256
```

Do not commit data copies or raw source archives merely to satisfy this check.

## Tool metric semantics

For release review, the current analytical-tool vocabulary uses these
definitions:

- A low score is `review_score <= 2`.
- Product revenue is `SUM(price)` and excludes freight.
- Category service metrics are grouped at one row per
  `order_id + product_category`.

These definitions describe the local tool outputs only; they are not a claim
that the dataset is complete, current, or fit for another purpose.
