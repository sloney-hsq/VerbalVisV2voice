# VerbalVis Compact Dashboard UI Design

## Objective

Make the dashboard easier to scan by giving the transcript predictable space,
removing decorative action styling, widening multi-series line charts, and
keeping newly created view titles short enough to display in full.

## Transcript

- The expanded transcript is exactly 250 pixels high, including its header.
- The collapsed transcript remains 40 pixels high.
- Empty and populated transcripts use the same expanded height; the current
  special compact empty state is removed.
- The transcript list remains the internal scrolling surface.

## Inline actions

- `Actions (N)` and its down caret are inline with the final assistant message
  in its conversation turn and use the same font size as the surrounding text.
- For an interrupted assistant message, the order is message text, the red
  interruption mark, then `Actions (N)` and its caret.
- If a turn has actions but no assistant message, the control follows the last
  visible message so that the actions remain reachable.
- The control has no tinted background, border, pill shape, or fixed button
  dimensions. Only a compact text label and caret remain.
- Expanded action summaries use neutral indentation without the current yellow
  panel treatment. Tool parameters and errors retain only the structure needed
  for readability.

## Multi-series line chart layout

- A view is a multi-series line chart when `chart_type` is `line` and `color`
  contains a series field.
- Such a card spans two dashboard grid columns by default.
- On a viewport that supports only one chart column, it falls back to one
  column and introduces no horizontal overflow.
- Other chart types and single-series line charts continue to occupy one
  column. Creation order remains unchanged.

## Short English view titles

- Every newly created view receives a concise English title of at most 40
  characters.
- The realtime prompt and tool schema tell the model to supply a short English
  title, but the backend is the final enforcement point.
- A supplied title is preserved only when it is short and uses English display
  text. Chinese or overlong titles are replaced with a canonical title composed
  from known metric, time grain, dimension, series, state, and Top-N labels.
- Canonical titles are assembled from complete words rather than cut at an
  arbitrary character boundary.
- Coordinated comparison views use the same concise title policy and do not
  copy an unchecked long or Chinese `title_prefix` into the displayed title.
- Updating an existing view preserves its current title unless the request
  explicitly supplies a replacement; a supplied replacement follows the same
  concise English rule.
- Existing views are not renamed merely because the application reloads.

## Components and data flow

- `transcriptGroups.js` identifies the message that anchors each turn's action
  control; `Dashboard.vue` renders the control in that message row.
- `chartLayout.js` owns the multi-series-line classification; `ChartSlot.vue`
  applies the corresponding two-column grid class.
- `backend/prompts.py` states the title rule. `backend/tools.py` validates or
  constructs titles before a new view is appended to dashboard state.
- No changes are required to the chart data, Vega-Lite encodings, realtime
  interruption policy, or tool-result ordering.

## Error and fallback behavior

- Actions remain accessible when an assistant response is missing or
  interrupted.
- A title that cannot be accepted is replaced deterministically; title
  formatting does not fail an otherwise valid chart request.
- The one-column chart fallback prevents a two-column span from creating an
  implicit overflowing grid track.

## Verification

- Unit tests cover action-anchor selection, multi-series-line classification,
  and accepted versus replaced view titles.
- The frontend production build and backend test suite must pass.
- Browser checks cover a populated 250-pixel transcript, inline interrupted
  actions, a two-column multi-series line chart, the one-column fallback, and a
  newly created view whose short English title is fully visible.

## Acceptance criteria

- Expanded transcript height computes to 250 pixels; collapsed height computes
  to 40 pixels.
- `Actions (N)` and its caret appear after the final assistant response or its
  red interruption mark, with no decorative fill or border.
- Multi-series line cards span two available grid columns and revert to one on
  narrow screens.
- New chart titles are concise English text no longer than 40 characters and
  are visible without ellipsis in representative dashboard cards.
- Existing voice, filter, highlight, chart rendering, and action expansion
  behavior continues to work.
