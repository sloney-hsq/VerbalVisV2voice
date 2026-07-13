# VerbalVis Compact Dashboard UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify transcript actions, fix the expanded transcript at 250 pixels, widen multi-series line charts to two grid columns, and guarantee short English titles for newly created views.

**Architecture:** Keep transcript grouping and chart classification as small pure JavaScript helpers, then let the existing Vue components render those decisions. Put deterministic title validation and canonical title construction in a pure Python module, while `backend/tools.py` remains responsible for applying it at view-creation boundaries. Preserve all realtime, chart-data, and Vega-Lite behavior.

**Tech Stack:** Vue 3, Pinia, native Node.js test runner, Python 3.12 `unittest`, FastAPI, DuckDB, Vega-Lite.

## Global Constraints

- Expanded transcript height is exactly `250px`; collapsed height remains `40px`.
- `Actions (N)` follows the final assistant message, or the red interruption mark when present, and has no background or border.
- A multi-series line is exactly `view.chart_type === "line" && Boolean(view.color)`.
- Multi-series lines span two available grid columns and fall back to one column on narrow screens without horizontal overflow.
- Every newly created view title is English display text with a maximum length of 40 characters.
- Existing views are not renamed on reload; an existing view is retitled only when `update_visual` explicitly receives `title`.
- Do not add runtime or test dependencies.
- Preserve the user's pre-existing uncommitted changes in `backend/prompts.py`, `backend/tools.py`, and the realtime/store files. Do not stage those unrelated changes.

---

### Task 1: Deterministic Short English View Titles

**Files:**
- Create: `backend/view_titles.py`
- Create: `backend/tests/test_view_titles.py`
- Modify: `backend/tools.py`
- Modify: `backend/prompts.py`

**Interfaces:**
- Consumes: validated chart fields already present in `backend/tools.py` (`chart_type`, `x_field`, `y_field`, `color`, `top_n`, `normalize`).
- Produces: `short_view_title(requested_title, *, chart_type, x, y, series=None, top_n=None, normalize=False, state=None) -> str` and `MAX_VIEW_TITLE_LENGTH = 40`.

- [ ] **Step 1: Write the failing title-policy tests**

Create `backend/tests/test_view_titles.py`:

```python
import unittest

from backend.view_titles import MAX_VIEW_TITLE_LENGTH, short_view_title


class ViewTitleTests(unittest.TestCase):
    def test_preserves_short_english_title(self):
        title = short_view_title(
            "Monthly Orders Trend",
            chart_type="line",
            x="order_month",
            y="order_count",
        )
        self.assertEqual(title, "Monthly Orders Trend")

    def test_replaces_chinese_title_with_canonical_english_title(self):
        title = short_view_title(
            "RJ州Top 5营收品类运营指标周度趋势",
            chart_type="line",
            x="order_week",
            y="order_count",
            series="product_category",
            top_n=5,
            state="RJ",
        )
        self.assertEqual(title, "RJ Weekly Orders (Top 5)")

    def test_replaces_overlong_title_without_cutting_a_word(self):
        title = short_view_title(
            "Weekly low score ratio trend for the five highest revenue categories",
            chart_type="line",
            x="order_week",
            y="low_score_ratio",
            series="product_category",
            top_n=5,
        )
        self.assertEqual(title, "Weekly Low-score Share (Top 5)")
        self.assertLessEqual(len(title), MAX_VIEW_TITLE_LENGTH)

    def test_builds_normalized_bar_title(self):
        title = short_view_title(
            "各州评分占比",
            chart_type="bar",
            x="customer_state",
            y="order_count",
            series="review_score",
            normalize=True,
        )
        self.assertEqual(title, "Review Score Share by State")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the title tests and verify RED**

Run:

```powershell
python -m unittest discover -s backend/tests -p 'test_view_titles.py' -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'backend.view_titles'`.

- [ ] **Step 3: Implement the pure title policy**

Create `backend/view_titles.py`:

```python
"""Short English display titles for dashboard views."""

from __future__ import annotations

import re
from typing import Any

MAX_VIEW_TITLE_LENGTH = 40

_METRIC_LABELS = {
    "order_count": "Orders",
    "product_revenue": "Revenue",
    "low_score_ratio": "Low-score Share",
    "delivery_days": "Delivery Days",
    "late_ratio": "Late Share",
    "review_score": "Review Score",
}
_DIMENSION_LABELS = {
    "order_month": "Month",
    "order_week": "Week",
    "order_date": "Date",
    "customer_state": "State",
    "product_category": "Category",
    "review_score": "Review Score",
}
_TIME_LABELS = {
    "order_month": "Monthly",
    "order_week": "Weekly",
    "order_date": "Daily",
}


def short_view_title(
    requested_title: Any,
    *,
    chart_type: str,
    x: str,
    y: str,
    series: str | None = None,
    top_n: int | None = None,
    normalize: bool = False,
    state: str | None = None,
) -> str:
    requested = " ".join(str(requested_title or "").split())
    if _is_short_english(requested):
        return requested

    suffix = _top_suffix(top_n)
    metric = _METRIC_LABELS.get(y, _field_label(y))
    dimension = _DIMENSION_LABELS.get(x, _field_label(x))
    series_label = _DIMENSION_LABELS.get(series or "", _field_label(series or ""))

    if chart_type == "scatter":
        bases = [f"{metric} vs {dimension}"]
    elif chart_type == "line":
        grain = _TIME_LABELS.get(x, dimension)
        if series and not suffix:
            bases = [f"{grain} {metric} by {series_label}", f"{grain} {metric}"]
        else:
            bases = [f"{grain} {metric}"]
    elif normalize and series:
        bases = [f"{series_label} Share by {dimension}", f"Share by {dimension}"]
    else:
        bases = [f"{metric} by {dimension}", f"{metric} Chart"]

    state_prefix = _state_prefix(state)
    candidates = [
        f"{state_prefix}{base}{suffix}".strip()
        for base in bases
    ] + [
        f"{base}{suffix}".strip()
        for base in bases
    ] + [
        f"{state_prefix}{base}".strip()
        for base in bases
    ] + [
        base for base in bases
    ]
    return next(
        (title for title in candidates if _is_short_english(title)),
        "Analytical View",
    )


def _is_short_english(title: str) -> bool:
    return (
        bool(title)
        and len(title) <= MAX_VIEW_TITLE_LENGTH
        and title.isascii()
        and bool(re.search(r"[A-Za-z]", title))
    )


def _top_suffix(value: int | None) -> str:
    try:
        top_n = int(value) if value is not None else 0
    except (TypeError, ValueError):
        top_n = 0
    return f" (Top {top_n})" if top_n > 0 else ""


def _state_prefix(value: str | None) -> str:
    state = str(value or "").strip()
    return f"{state.upper()} " if re.fullmatch(r"[A-Za-z]{2}", state) else ""


def _field_label(value: str) -> str:
    return str(value or "View").replace("_", " ").title()
```

- [ ] **Step 4: Run the title tests and verify GREEN**

Run:

```powershell
python -m unittest discover -s backend/tests -p 'test_view_titles.py' -v
```

Expected: `Ran 4 tests` and `OK`.

- [ ] **Step 5: Apply the policy at backend view-creation boundaries**

In `backend/tools.py`, import `short_view_title`, describe both tool title fields as `Short English display title, at most 40 characters`, and make these targeted changes:

```python
from view_titles import short_view_title
```

For coordinated comparison views, replace the display-title assembly with:

```python
title = short_view_title(
    None,
    chart_type=chart_type,
    x=x,
    y=metric,
    series=series,
    top_n=top_n,
    state=args.get("customer_state"),
)
```

Immediately after `_exec_create_visual` obtains a valid candidate, normalize the requested title:

```python
candidate["title"] = short_view_title(
    args.get("title"),
    chart_type=candidate["chart_type"],
    x=candidate["x_field"],
    y=candidate["y_field"],
    series=candidate.get("color"),
    top_n=candidate.get("top_n"),
    normalize=bool(candidate.get("normalize")),
)
```

After `_exec_update_visual` builds its candidate, normalize only an explicitly supplied replacement:

```python
if "title" in args:
    candidate["title"] = short_view_title(
        args.get("title"),
        chart_type=candidate["chart_type"],
        x=candidate["x_field"],
        y=candidate["y_field"],
        series=candidate.get("color"),
        top_n=candidate.get("top_n"),
        normalize=bool(candidate.get("normalize")),
    )
```

In `backend/prompts.py`, add this stable rule near the visualization routing instructions without replacing the user's current prompt edits:

```text
create_visual 和 update_visual 的 title 必须是最多 40 个字符的简短英文，不得使用中文，也不要把完整查询复述进标题。compare_category_metrics 的显示标题同样保持简短英文。
```

- [ ] **Step 6: Re-run backend tests and inspect only the intended backend diff**

Run:

```powershell
python -m unittest discover -s backend/tests -p 'test_view_titles.py' -v
git diff -- backend/view_titles.py backend/tests/test_view_titles.py backend/tools.py backend/prompts.py
```

Expected: all four tests pass; the diff preserves the pre-existing prompt and tool changes and adds only the title policy.

- [ ] **Step 7: Preserve dirty-worktree ownership**

Do not commit or stage `backend/prompts.py` or `backend/tools.py`, because both contained user changes before this task. Leave the integrated backend changes visible in the working tree for final review.

---

### Task 2: Fixed Transcript Height and Inline Minimal Actions

**Files:**
- Create: `frontend/tests/transcriptGroups.test.js`
- Modify: `frontend/package.json`
- Modify: `frontend/src/transcriptGroups.js`
- Modify: `frontend/src/components/Dashboard.vue`

**Interfaces:**
- Consumes: the existing `groupTranscriptItems(items)` flat timeline input.
- Produces: each returned group gains `actionAnchorId: string | null`, preferring its final assistant message and falling back to its final visible message.

- [ ] **Step 1: Write failing action-anchor tests and add the native test command**

Create `frontend/tests/transcriptGroups.test.js`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

import { groupTranscriptItems } from "../src/transcriptGroups.js";

test("anchors actions after the final assistant message", () => {
  const [group] = groupTranscriptItems([
    { id: "user-1", role: "user", text: "Show me" },
    { id: "assistant-1", role: "assistant", text: "First response" },
    { id: "tool-1", role: "tool", summary: "create visual" },
    { id: "assistant-2", role: "assistant", text: "Interrupted", status: "interrupted" },
  ]);

  assert.equal(group.actionAnchorId, "assistant-2");
});

test("falls back to the final visible message when no assistant exists", () => {
  const [group] = groupTranscriptItems([
    { id: "user-1", role: "user", text: "Show me" },
    { id: "tool-1", role: "tool", summary: "create visual" },
  ]);

  assert.equal(group.actionAnchorId, "user-1");
});
```

Add to `frontend/package.json` scripts:

```json
"test": "node --test tests/*.test.js"
```

- [ ] **Step 2: Run the transcript tests and verify RED**

Run:

```powershell
npm test -- --test-name-pattern="anchors|falls back"
```

Working directory: `frontend`.

Expected: two assertion failures because `actionAnchorId` is currently `undefined`.

- [ ] **Step 3: Add the action anchor to transcript grouping**

In `frontend/src/transcriptGroups.js`, finalize groups before returning them:

```javascript
  groups.forEach((group) => {
    group.actionAnchorId = actionAnchorId(group.messages);
  });
  return groups;
}

function actionAnchorId(messages) {
  for (let index = messages.length - 1; index >= 0; index -= 1) {
    if (messages[index]?.role === "assistant") return messages[index].id || null;
  }
  return messages[messages.length - 1]?.id || null;
}
```

Initialize `actionAnchorId: null` in `makeGroup` so every returned group has a stable shape.

- [ ] **Step 4: Run the transcript tests and verify GREEN**

Run:

```powershell
npm test -- --test-name-pattern="anchors|falls back"
```

Working directory: `frontend`.

Expected: two tests pass.

- [ ] **Step 5: Move the Actions control into the anchor message row**

In `Dashboard.vue`, place the existing button after `.interrupted-mark` inside `.timeline-row__body` and gate it with:

```vue
<button
  v-if="group.actions.length && group.actionAnchorId === item.id"
  class="actions-toggle"
  type="button"
  :aria-expanded="isGroupActionsOpen(group.id)"
  @click="toggleGroupActions(group.id)"
>
  <span>Actions ({{ group.actions.length }})</span>
  <span aria-hidden="true">{{ isGroupActionsOpen(group.id) ? '⌃' : '⌄' }}</span>
</button>
```

Delete the standalone Actions button below the message loop. Keep `.action-list` after the loop so expanded details remain directly beneath the anchored final message.

- [ ] **Step 6: Replace transcript and action decoration CSS with the approved compact rules**

Make the expanded timeline exact and remove the empty-height override:

```css
.timeline {
  flex: 0 0 250px;
  height: 250px;
}

.timeline--collapsed {
  flex-basis: 40px;
  height: 40px;
}
```

Remove the `timeline--empty` modifier binding and CSS block. Remove the mobile clamp override so `250px` remains exact.

Split `.actions-toggle` from the decorated `.timeline__toggle` rules and use:

```css
.actions-toggle {
  display: inline-flex;
  align-items: baseline;
  align-self: flex-start;
  flex: 0 0 auto;
  margin: 0;
  padding: 0;
  gap: 2px;
  border: 0;
  background: transparent;
  color: #64748b;
  cursor: pointer;
  font: inherit;
  font-size: inherit;
  font-weight: 600;
  line-height: 1.35;
  white-space: nowrap;
}

.actions-toggle:hover { color: #1d5ec7; }

.action-list {
  margin: 1px 0 3px 98px;
  padding: 0;
  background: transparent;
}
```

Remove yellow borders/backgrounds from `.action-list`, `.tool-summary`, and `.tool-details`; use neutral slate borders/text while preserving red error styling and readable indentation.

- [ ] **Step 7: Run frontend tests and production build**

Run:

```powershell
npm test
npm run build
```

Working directory: `frontend`.

Expected: two tests pass and Vite exits with code 0.

---

### Task 3: Two-Column Multi-Series Line Cards

**Files:**
- Create: `frontend/tests/chartLayout.test.js`
- Modify: `frontend/src/chartLayout.js`
- Modify: `frontend/src/components/ChartSlot.vue`

**Interfaces:**
- Consumes: a frontend view object with `chart_type` and optional `color`.
- Produces: `isMultiSeriesLine(view) -> boolean`, used by `ChartSlot.vue` to apply `chart-card--multi-series`.

- [ ] **Step 1: Write the failing chart-layout tests**

Create `frontend/tests/chartLayout.test.js`:

```javascript
import test from "node:test";
import assert from "node:assert/strict";

import { isMultiSeriesLine } from "../src/chartLayout.js";

test("identifies a line chart with a series", () => {
  assert.equal(isMultiSeriesLine({
    chart_type: "line",
    color: "product_category",
  }), true);
});

test("keeps single-series lines and other chart types at one column", () => {
  assert.equal(isMultiSeriesLine({ chart_type: "line", color: null }), false);
  assert.equal(isMultiSeriesLine({ chart_type: "bar", color: "review_score" }), false);
});
```

- [ ] **Step 2: Run the chart-layout tests and verify RED**

Run:

```powershell
npm test -- --test-name-pattern="series|column"
```

Working directory: `frontend`.

Expected: module import failure because `isMultiSeriesLine` is not exported yet.

- [ ] **Step 3: Implement the pure classification and card class**

In `frontend/src/chartLayout.js`, add:

```javascript
export function isMultiSeriesLine(view) {
  return view?.chart_type === "line" && Boolean(view?.color);
}
```

Update the existing comment so it no longer claims every view always occupies one grid cell.

In `ChartSlot.vue`, import the helper and add this root class binding:

```vue
'chart-card--multi-series': isMultiSeriesLine(view),
```

Add the grid rule and narrow fallback:

```css
.chart-card--multi-series {
  grid-column: span 2;
}

@media (max-width: 850px) {
  .chart-card--multi-series {
    grid-column: span 1;
  }
}
```

- [ ] **Step 4: Run all frontend tests and build**

Run:

```powershell
npm test
npm run build
```

Working directory: `frontend`.

Expected: four tests pass and Vite exits with code 0.

---

### Task 4: Integrated Verification and Visual Acceptance

**Files:**
- Verify: `backend/view_titles.py`
- Verify: `backend/tools.py`
- Verify: `backend/prompts.py`
- Verify: `frontend/src/transcriptGroups.js`
- Verify: `frontend/src/chartLayout.js`
- Verify: `frontend/src/components/Dashboard.vue`
- Verify: `frontend/src/components/ChartSlot.vue`

**Interfaces:**
- Consumes: the completed backend title policy and frontend grouping/layout behavior from Tasks 1–3.
- Produces: fresh test, build, diff, and browser evidence for every acceptance criterion.

- [ ] **Step 1: Run the full local verification suite**

Run from the repository root:

```powershell
python -m unittest discover -s backend/tests -p 'test_*.py' -v
Push-Location frontend
npm test
npm run build
Pop-Location
git diff --check
```

Expected: backend tests pass, frontend tests pass, Vite exits 0, and `git diff --check` exits 0.

- [ ] **Step 2: Review scope and ownership before browser testing**

Run:

```powershell
git status --short
git diff --stat
git diff -- frontend/src/transcriptGroups.js frontend/src/chartLayout.js frontend/src/components/Dashboard.vue frontend/src/components/ChartSlot.vue frontend/package.json backend/view_titles.py backend/tests/test_view_titles.py backend/tools.py backend/prompts.py
```

Expected: no unrelated files were edited by this implementation; pre-existing user changes remain present and unstaged.

- [ ] **Step 3: Start the local app and perform browser measurements**

Load the `browser:control-in-app-browser` skill before using browser tools. Start the backend with `python -m uvicorn main:app --app-dir backend --host 127.0.0.1 --port 8000` and the frontend with `npm run dev -- --host 127.0.0.1` from `frontend`, both as hidden background processes.

At a wide viewport, inspect computed styles and DOM order:

```javascript
({
  transcriptHeight: getComputedStyle(document.querySelector('.timeline')).height,
  actionBackground: getComputedStyle(document.querySelector('.actions-toggle')).backgroundColor,
  actionBorder: getComputedStyle(document.querySelector('.actions-toggle')).borderStyle,
  actionParent: document.querySelector('.actions-toggle')?.parentElement?.className,
  multiSeriesColumn: getComputedStyle(document.querySelector('.chart-card--multi-series')).gridColumnEnd,
})
```

Expected: `250px`, transparent background, no border, a `.timeline-row__body` parent, and a two-column span. Verify the interrupted DOM order is message text, interruption mark, Actions. Verify a newly created Chinese/long requested title is displayed as short English text no longer than 40 characters without ellipsis.

- [ ] **Step 4: Verify the narrow fallback**

Resize the browser below 850 pixels and inspect the multi-series card.

Expected: `grid-column` resolves to a one-column span and the page has no horizontal overflow (`document.documentElement.scrollWidth === document.documentElement.clientWidth`).

- [ ] **Step 5: Final requirement audit**

Check each design acceptance criterion against fresh evidence:

```text
[ ] Expanded transcript is 250px; collapsed transcript is 40px.
[ ] Actions is inline after Assistant or the red interruption mark.
[ ] Actions and expanded action details have no yellow/tinted decoration.
[ ] Multi-series line charts span two columns and fall back to one.
[ ] New titles are English, <= 40 characters, and fully visible.
[ ] Existing chart rendering, action expansion, filters, highlights, and voice code still build.
```

Do not claim completion until every item has direct test, build, diff, or browser evidence.
