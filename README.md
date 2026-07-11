# VerbalVis-FD-Voice

VerbalVis-FD-Voice is a voice-only conversational visual analytics prototype for
the Olist dashboard. It supports continuous microphone input, Qwen Semantic VAD,
assistant speech, dashboard tools, barge-in during assistant playback, coordinated
visual updates, and experiment logs.

Text-CVA, Voice/Text switching, text input, `/ws/text`, and `/ws/qwen` are not part
of this repository. Text-CVA is maintained as a separate experimental condition.

## Research and Runtime Boundary

The formal study compares the complete **FD-Voice** and **Text-CVA** configurations.
The result must be described as differences between the two configurations, not as
a causal effect of full-duplex interaction alone.

FD-Voice supports user interruption while assistant speech is being generated or
played. Dashboard tool execution is intentionally non-preemptive: after a tool
batch starts, it finishes normally before the next analytical request is accepted.
The prototype does not implement stale-tool invalidation, intent epochs, rollback,
transactions, or tool-thread cancellation.

During a tool batch:

- the frontend stops forwarding microphone chunks;
- the backend ignores any remaining microphone chunks;
- the batch uses the completed user transcript captured for that response;
- calls execute sequentially in model-returned order;
- the browser receives explicit tool and dashboard state events;
- microphone streaming resumes after the post-tool response is requested.

There is no artificial tool-call cap. The model may perform all actions needed for
an analysis, but the model-facing tool surface is kept small to reduce ambiguous
or invalid choices.

## Final Model-Facing Tool Set

Qwen sees six tools.

### 1. `update_analysis_scope`

Manages the shared global data scope.

- `operation="replace"`: start a new scope;
- `operation="add"`: add conditions to the current scope;
- `operation="remove"`: remove filters by field;
- `operation="clear"`: clear all global filters.

Example:

```json
{
  "operation": "replace",
  "filters": [
    {"field": "customer_state", "operator": "eq", "value": "SP"},
    {
      "field": "order_date",
      "operator": "between",
      "value": ["2017-10-01", "2018-05-31"]
    }
  ]
}
```

The older `filter_data`, `remove_filter`, and `set_analysis_scope` functions remain
internal compatibility code but are not exposed to Qwen.

### 2. `create_visual`

Creates one free-exploration visualization. It exposes a shorter and safer schema
than the internal `append_visual` engine:

- `chart_type`;
- `x` and `y`;
- optional `series`;
- `title`;
- optional `top_n`, sorting, local filters, global-scope inheritance, snapshot,
  and overall series.

Use it for one custom chart. Use `compare_category_metrics` when several metrics
must compare exactly the same category set.

### 3. `compare_category_metrics`

Creates coordinated views and evidence for one common Top-N product-category set.
It first computes and validates all requested views, then commits the whole group
to the Dashboard. A failed preparation therefore does not leave half of a
comparison group behind.

Modes:

- `weekly_trends`: one weekly multi-series line chart per metric;
- `category_summary`: one category bar chart per metric.

Important arguments:

- `top_n`;
- `rank_by="product_revenue"` or `rank_by="order_count"`;
- `metrics`;
- optional `focus_week`, such as `2017-W48`;
- `replace_previous=true` by default to prevent repeated comparison groups from
  filling the Dashboard.

### 4. `delete_visual`

Deletes one view by `view_id`. Other views and the global analysis scope are kept.

### 5. `highlight_visual`

Focuses one or more views and can highlight real data marks inside those views.
Supported `highlight_element` examples:

```text
2017-W48
office_furniture
order_week=2017-W48
order_week=2017-W48, product_category=office_furniture
```

The frontend resolves these values against each highlighted view's actual data.
Line charts can emphasize a series, a week, or their intersection. Bar, scatter,
pie, and table views reduce nonmatching marks or rows and emphasize matches.
Unmatched values do not incorrectly dim the entire chart.

### 6. `inspect_visual`

Reads one current view and returns its encoding, filter scope, statistics, data
point count, returned rows, and a `truncated` flag. When `truncated=true`, returned
rows are only a subset and must not be treated as the complete chart.

## Internal Tool Layer

The existing primitive implementations remain in `backend/tools.py` for reuse:

- `filter_data`;
- `remove_filter`;
- `append_visual`;
- `set_low_score_threshold`;
- `delete_visual`;
- `highlight_visual`;
- `inspect_visual`.

Only deletion, highlighting, and inspection are exposed directly. Scope updates
and chart creation are exposed through the safer wrappers above.

## Fixed Study Metric Semantics

### Low-score definition

Low-score orders are fixed as:

```text
review_score <= 2
```

`set_low_score_threshold` is not exposed to Qwen. This prevents different charts
or filters from silently using inconsistent low-score definitions during the
experiment.

### Product revenue

Category revenue means product-price revenue:

```sql
SUM(price)
```

Freight is excluded. The base Category Revenue Top-15 view and coordinated
comparisons use this definition. Results expose it as `product_revenue` even
though the frontend-compatible view field remains `revenue` internally.

### Category delivery grain

For category delivery metrics, an order is counted once per product category.
The query first creates one row per `order_id + product_category`, then computes
average delivery time or ratios. An order containing multiple items from the same
category is therefore not given extra weight.

## Demo Coverage

### Task A: SP peak-period operations

Reliable path:

1. `update_analysis_scope` with SP and 2017-10-01 through 2018-05-31;
2. `compare_category_metrics` with:
   - `mode="weekly_trends"`;
   - `top_n=5`;
   - `rank_by="product_revenue"`;
   - metrics `order_count`, `low_score_ratio`, `delivery_days`, `late_ratio`;
   - `focus_week="2017-W48"`.

This creates four weekly multi-series line charts using one common product-revenue
Top-5 set and returns, for every category and metric, the peak week/value, focus
week/value, and top weeks.

### Task B: RJ delivery-resource allocation

Reliable path:

1. `update_analysis_scope` with RJ and 2017-10-01 through 2018-05-31;
2. `compare_category_metrics` with:
   - `mode="category_summary"`;
   - `top_n=15`;
   - `rank_by="product_revenue"`;
   - metrics `low_score_ratio`, `delivery_days`, `product_revenue`, `order_count`.

This creates four bar charts for the same product-revenue Top-15 set and returns a
compact evidence row for each category, including `office_furniture` when the data
premise holds.

These paths are recommendations, not fixed scripts. The user and model may change
scope, inspect a chart, create another view, delete obsolete views, highlight a
week or category, or redirect the analysis.

## Dashboard State Feedback

The frontend runtime panel shows the current phase, active tools, global filter
count, view count, fixed low-score definition, filtered row count, and tool errors.
It does not add direct-manipulation controls that would change the voice-only study
condition.

## Validation

Backend validation does not call Qwen. It checks the model-facing tool set, fixed
low-score definition, base product-revenue view, Task A coordinated weekly views,
Task B coordinated category views, `office_furniture` membership, product revenue
against `SUM(price)`, and delivery time against a distinct order-category query.

```bat
cd /d F:\VerbalVis2\backend
python -m compileall .
python demo_validation.py
```

Frontend validation checks in-chart highlighting and the production build:

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run validate:highlight
npm run build
```

The GitHub workflow `.github/workflows/validate-fd-voice.yml` runs backend compile,
Task A/B validation, and frontend build on pushes to `fd-voice`.

## Start

```env
DASHSCOPE_API_KEY=你的API_KEY
QWEN_REGION=beijing
```

```bat
cd /d F:\VerbalVis2\backend
uvicorn main:app --reload --port 8000
```

```bat
cd /d F:\VerbalVis2\frontend
npm install
npm run dev -- --port 5173
```

Open `http://localhost:5173`.
