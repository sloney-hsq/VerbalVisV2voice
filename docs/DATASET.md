# Dataset contract

## Scope and local location

VerbalVis reads a local copy of the Olist CSV dataset from
`backend/data/olist/`. The repository tracks local CSV copies in that
directory as development and research inputs. The application does not fetch
or serve dataset files. This repository remains a standalone prototype and is
not wired to a dataset distribution service.

## Source, attribution, and reuse boundary

The CSV snapshot in this repository is third-party material. It is the
[Brazilian E-Commerce Public Dataset by Olist on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(`olistbr/brazilian-ecommerce`), attributed by the source metadata to
**Francisco Magioli**. The observed source metadata for this release identifies
current version **2**, last updated **2021-10-01**, under
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/).

The root [MIT License](../LICENSE) applies to repository-authored software and
documentation, not to `backend/data/olist/`. Do not represent the Olist data
as MIT-licensed or commercially reusable. Review and comply with the source
license before any use, sharing, or redistribution of the data. This is a
release boundary, not legal advice; the source terms remain authoritative. See
the root [third-party notices](../THIRD_PARTY_NOTICES.md) for the concise
attribution notice.

## Expected source files

`backend/db.py` reads these CSV files:

- `olist_orders_dataset.csv`
- `olist_order_items_dataset.csv`
- `olist_order_reviews_dataset.csv`
- `olist_customers_dataset.csv`
- `olist_products_dataset.csv`
- `olist_order_payments_dataset.csv`
- `product_category_name_translation.csv`

## Integrity procedure

The known-good SHA-256 values for the exact repository snapshot are in
[`olist-data-sha256.txt`](olist-data-sha256.txt). Run this from the repository
root to compare every recorded file:

```powershell
$failures = foreach ($line in Get-Content docs/olist-data-sha256.txt) {
    if (!$line -or $line.StartsWith("#")) { continue }
    $parts = $line -split "\s{2,}", 2
    $actual = (Get-FileHash -LiteralPath $parts[0] -Algorithm SHA256).Hash
    if ($actual -ne $parts[1]) { "$($parts[0]): expected $($parts[1]), got $actual" }
}
if ($failures) { $failures; throw "Olist snapshot checksum verification failed." }
"Olist snapshot checksums match."
```

The manifest inventories every local CSV in the directory (currently nine),
including files not loaded by `backend/db.py`. The runtime subset is the seven
files listed above, including the translation file. It verifies only the exact
repository snapshot; it does **not** establish the original upstream
provenance or replace review of the source license. Do not add additional data
copies or raw source archives merely to satisfy this check.

## Tool metric semantics

For release review, the current analytical-tool vocabulary uses these
definitions:

- A low score is `review_score <= 2`.
- Product revenue is `SUM(price)` and excludes freight.
- Category service metrics are grouped at one row per
  `order_id + product_category`.

These definitions describe the local tool outputs only; they are not a claim
that the dataset is complete, current, or fit for another purpose.
