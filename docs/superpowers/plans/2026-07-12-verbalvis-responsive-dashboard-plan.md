# VerbalVis Responsive Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a fluid 4/3/2/1-column analytical workspace and a bottom conversation transcript that hides each turn's tools behind one `Actions (N)` control.

**Architecture:** Keep the existing Vue/Pinia/WebSocket architecture. Add one pure transcript grouping module, let `Dashboard.vue` own only presentation state for panel/group expansion, and replace fixed dimensions with container-driven CSS. Vega specifications and backend protocol remain unchanged.

**Tech Stack:** Vue 3, Pinia, CSS Grid, Vega-Lite 6, Node validation scripts.

## Global Constraints

- All views use one uniform responsive placement policy.
- Representative widths 1920, 1280, 900, and 600 render 4, 3, 2, and 1 columns.
- Conversation text is visible while the transcript is expanded.
- Tools are hidden until the user opens the turn's `Actions (N)` control.
- Existing response-id, revision, highlight, Task A, and Task B behavior must not change.

---

### Task 1: Pure conversation-turn grouping

**Files:**
- Create: `frontend/src/transcriptGroups.js`
- Create: `frontend/scripts/validate-transcript-groups.mjs`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: chronological transcript items with `id`, `role`, `startedAt`.
- Produces: `groupTranscriptItems(items) -> [{ id, messages, actions, startedAt }]`.

- [ ] **Step 1: Write the failing grouping validation**

Validate that two user turns remain separate, user/assistant items stay visible in
`messages`, and all tool items move to `actions` without appearing in messages.

- [ ] **Step 2: Run the validation and verify RED**

Run: `node frontend/scripts/validate-transcript-groups.mjs`

Expected: failure because `transcriptGroups.js` does not exist.

- [ ] **Step 3: Implement the pure grouping function**

Start a group for every user item. Attach following assistant/tool items until
the next user item. Use a stable fallback group for items received before the
first user transcript.

- [ ] **Step 4: Run the validation and verify GREEN**

Run: `npm run validate:transcript`

Expected: `Transcript grouping validation: PASS`.

### Task 2: Responsive chart workspace and transcript UI

**Files:**
- Modify: `frontend/src/components/Dashboard.vue`
- Modify: `frontend/src/components/ChartSlot.vue`
- Modify: `frontend/scripts/validate-layout.mjs`

**Interfaces:**
- Consumes: `groupTranscriptItems(store.transcriptItems)`.
- Produces: responsive chart grid, `timelineCollapsed`, and one group-level
  `Actions (N)` disclosure.

- [ ] **Step 1: Add failing source-contract assertions**

Require an `auto-fit` grid with `minmax(min(100%, 400px), 1fr)`, no card
`max-width: 540px`, a collapsed transcript class, conversation groups, and the
literal `Actions (` label.

- [ ] **Step 2: Run `npm run validate:layout` and verify RED**

Expected: failure against the current fixed two-column CSS and flat transcript.

- [ ] **Step 3: Implement the responsive workspace**

Use:

```css
grid-template-columns: repeat(auto-fit, minmax(min(100%, 400px), 1fr));
```

Remove card maximum width, use a compact responsive height, and keep chart
overflow inside the workspace rather than individual cards.

- [ ] **Step 4: Implement transcript presentation state**

The transcript is expanded by default and collapses to a compact header. Render
message rows immediately. Render no tool rows until the group's `Actions (N)`
button is open; retain the existing per-tool detail toggle inside the revealed
action list.

- [ ] **Step 5: Run frontend validations and build**

Run:

```powershell
npm run validate:transcript
npm run validate:layout
npm run validate:highlight
npm run validate:normalized
npm run validate:session
npm run build
```

Expected: all validations pass and Vite exits 0.

### Task 3: Browser viewport acceptance

**Files:**
- Modify: `.github/workflows/validate-fd-voice.yml`

**Interfaces:**
- Consumes: built frontend served by the existing FastAPI application.
- Produces: recorded evidence for column count, overflow, transcript disclosure,
  and real SVG rendering.

- [ ] **Step 1: Add transcript validation to CI**

Add `npm run validate:transcript` before the frontend build.

- [ ] **Step 2: Build and open the real application at four viewport widths**

At 1920, 1280, 900, and 600 pixels verify column counts 4, 3, 2, and 1,
`scrollWidth <= clientWidth`, and one SVG per base chart.

- [ ] **Step 3: Verify transcript behavior**

Confirm that conversation text is visible, tool rows are absent before opening
`Actions (N)`, tool rows appear after opening it, and collapsing/reopening the
panel preserves conversation content.

- [ ] **Step 4: Run the full repository regression**

Run backend compile, `coordination_validation.py`, `demo_validation.py`, every
frontend validation, `npm run build`, and `git diff --check`.
