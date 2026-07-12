# VerbalVis Responsive Dashboard Design

## Objective

Replace the fixed two-column dashboard with a viewport-driven analytical
workspace while preserving the original bottom transcript interaction. The
interface must prioritize visual comparison, keep conversation text visible,
and hide tool actions until the user asks to inspect them.

## Responsive workspace

- The page remains a full-viewport application with a compact header, one
  scrollable chart workspace, and a bottom transcript panel.
- The chart workspace uses one uniform `auto-fit` grid. Cards have no fixed
  maximum width and expand to fill their grid tracks.
- Expected visual density is four columns on very wide screens, three columns
  on ordinary desktop screens, two columns on tablet/small desktop screens,
  and one column on narrow mobile screens.
- These are behavior targets rather than four unrelated hard-coded layouts;
  the minimum card width and available container width determine the result.
- All views use the same placement policy. Task A and Task B views stay
  adjacent in creation order, but are not forced into a fixed 2x2 matrix.
- Chart cards use a consistent compact height. Vega remains responsive inside
  each card. Charts do not introduce their own scrollbars.
- The chart workspace is the primary scrolling surface when all views cannot
  fit above the transcript.

## Header

- Wide screens keep brand, runtime state, filters, and microphone on one row.
- Medium screens move filter chips to a second row without reducing chart
  width unnecessarily.
- Narrow screens shorten secondary brand text but keep runtime status and the
  microphone action visible.

## Transcript

- The transcript stays at the bottom and is expanded by default.
- A header control collapses the panel to a compact status bar of roughly 40
  pixels; expanding it restores the conversation without losing scroll state.
- Expanded height is compact and responsive rather than a fixed 250 pixels.
- User and assistant conversation text is always visible while expanded.
- Timeline items are presented as conversation turns. A turn begins with a
  user utterance and contains the assistant responses and tools that follow it
  until the next user utterance.
- Tool items are hidden by default. A turn with tools shows one `Actions (N)`
  button. Clicking it reveals all tool summaries for that turn.
- An individual tool summary can then be expanded to show parameters and an
  error. Successful internal result payloads remain hidden from the normal
  transcript.
- Interrupted assistant responses retain their interruption marker.
- New conversation content scrolls the transcript to the latest turn unless
  the user is inspecting an expanded action.

## Error behavior

- A chart render failure is contained inside its card and does not change grid
  placement.
- Long titles and badges use truncation and accessible hover text.
- Long action details scroll within the expanded action, not the whole page.
- Responsive state is CSS-driven and does not create or reconnect a Realtime
  session.

## Acceptance criteria

- At representative 1920, 1280, 900, and 600 pixel widths, the workspace uses
  4, 3, 2, and 1 chart columns respectively without horizontal
  overflow.
- Cards fill their tracks and no longer remain fixed at 540 pixels.
- The four base views render one SVG each at every representative width.
- The transcript is visible by default, can collapse and reopen, and never
  covers the chart workspace.
- Conversation text remains visible; tool rows are absent until the matching
  `Actions (N)` control is opened.
- Existing highlight, voice interruption, revision gating, Task A, and Task B
  validations continue to pass.
