# TextifAI UI Review Checklist

## Dashboard Checklist
- Is ingestion status visible?
- Are chapter/review/retry counts easy to scan?
- Is next action obvious?
- Are empty states useful?

## Graph Readability Checklist
- Are labels readable without overlap?
- Does node size reflect useful signal like degree?
- Are filters available and understandable?
- Is local graph available?
- Is selected node state obvious?

## Wiki / Browser Checklist
- Can author browse Markdown notes easily?
- Are backlinks visible?
- Are tags visible and useful?
- Is search present or planned clearly?
- Is preview available?

## Node Detail Checklist
- Are aliases visible?
- Are facts visible?
- Are relationships visible?
- Are source/evidence pointers visible?
- Is review status visible?
- Is there a clear edit affordance?

## Editor / AI Suite Checklist
- Is chapter editing central, not hidden?
- Are line/paragraph AI tools scoped and grounded?
- Is Character Lab discoverable?
- Are AI suggestions tied to VaERL context?

## Author-facing Language Checklist
- Avoid chunk/reduction/provider/token jargon in primary UX.
- Prefer chapter/story/review/result language.
- Make CTA verbs clear.

## Debug Secondary Checklist
- Are raw JSON and artifacts clearly secondary?
- Can author ignore debug surfaces safely?

## No Internal Terms Checklist
- Hide run_id / provider / telemetry / failure_mode from primary author views.
- Show internal terms only in debug/dev contexts.

## Responsive Layout Checklist
- Sidebar remains usable on smaller widths.
- Graph/detail split degrades cleanly.
- Note reading width remains comfortable.
- Buttons remain clickable and labeled.
