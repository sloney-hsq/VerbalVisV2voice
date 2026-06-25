# Fig. 1 Teaser Prompt for VerbalVis

Use this prompt to recreate or refine the VerbalVis main figure in Figma, Illustrator, or an image-generation/design assistant. This prompt is aligned with the current VerbalVis implementation: native full-duplex Realtime speech, schema-based tool calls, stale tool-call invalidation, and compact dashboard-context reinjection. Do not depict runtime classification of Goal Shift / Hypothesis Correction / Scope Narrowing; those are paper-level analytical categories, not dispatch branches in the implemented system.

```text
Design Figure 1 (Teaser) for a TVCG-style paper titled:
"VerbalVis: Supporting Analytical Intent Evolution through Full-Duplex Conversational Visual Analytics".

Goal:
The figure must show why VerbalVis is more than a generic voice dashboard. It should communicate that a user can interrupt the assistant mid-response, and that the interruption synchronizes three internal system layers: voice/realtime control, schema-based analytical tool calls, and dashboard state reinjection.

Canvas:
- 1800 x 1000 px.
- White background (#FFFFFF).
- Academic visual style: clean lines, no gradients, no shadows, no decorative blobs.
- Use blue (#2563EB) for user/realtime input, purple (#8B5CF6) for assistant speech, orange (#F97316) for barge-in/cancel events, green (#10B981) for successful replanning/dashboard update, gray (#6B7280/#E5E7EB) for structure.

Overall layout:
- Top half: a three-panel storyboard from the user perspective.
- Bottom half: a system activity trace with three synchronized swimlanes.
- Bottom edge: a time axis from t=0s to t=12s.

Top storyboard:
Panel 1, "Initial analytical intent":
- Show a simple dashboard chart titled "Sales by State".
- User speech bubble: "Show me sales by state."
- Small tool annotation: append_visual / highlight state view.

Panel 2, "User barges in":
- Show the previous chart with an orange cancellation mark.
- Assistant bubble or label: "System canceled".
- User interrupt bubble: "Actually, show me by product category instead."
- Emphasize that this happens while the assistant is still speaking.

Panel 3, "Replanned dashboard":
- Show a simple dashboard chart titled "Sales by Category".
- Assistant bubble: "Switching to category view..."
- Connect Panel 2 to Panel 3 with an orange arrow labeled "cancel and replan".

System activity trace:
Create three horizontal lanes that share the same x-axis alignment:

Lane 1: Voice / Realtime
- Label: "Voice", subtitle "user <-> gpt-realtime-2".
- Draw waveform segments:
  - t=0-2s blue user waveform: "show sales by state".
  - t=2-4.3s purple assistant waveform: "explaining state pattern...".
  - t=4.3s orange vertical line, orange dot, label "BARGE-IN".
  - t=4.3-6s blue user waveform: "switch to product category".
  - t=6.5-11s purple assistant waveform: "switching to category view...".

Lane 2: Tools / Controller
- Label: "Tools", subtitle "schema-based controller".
- Place tool-call blocks aligned to time:
  - Around t=2s: blue block "append_visual" or "highlight_visual", with small note "state view".
  - At t=4.3s: orange block "response.cancel", with small note "truncate audio; invalidate epoch".
  - Around t=6.5s: green block "append_visual", with small note "bar, x=product_category".
  - Optional gray/black block after cancel: "stale guard", with small note "discard old tool results".
- The orange response.cancel block should be circled or otherwise emphasized.

Lane 3: Dashboard / Context
- Label: "Dashboard", subtitle "context reinjected".
- Use JSON-like state cards:
  - Pre-interruption card:
    { charts: [state_bar], highlighted: null }
  - Cancellation card:
    { status: CANCELED, stale: dropped, reinject: context }
  - Replanned card:
    { charts: [state_bar, category_bar], active: category }
  - Context card:
    "system message: latest filters + view stats".

Critical alignment:
- Events at t=4.3s must form one vertical orange line across all three lanes.
- Add a small callout near that line: "three-layer synchronization".
- Add a second blue vertical guide around t=6.5s with callout: "replanning grounded in state".
- The bottom time axis must include ticks: t=0s, t=4s, t=4.3s barge-in, t=8s, t=12s.

Important semantic constraints:
- Do not show VerbalVis as explicitly detecting Goal Shift / Hypothesis Correction / Scope Narrowing at runtime.
- Do show that barge-in is handled uniformly: cancel/truncate the old response, invalidate stale tools, execute new tool calls, reinject dashboard context, continue from the latest user intent.
- Do not imply that dashboard context is a huge full transcript. Show compact reinjection: active filters, highlighted view, available views, and per-view statistics.
- Keep all labels short enough to be readable in a single-column paper figure preview.
```

