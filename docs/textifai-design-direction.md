# TextifAI Design Direction

## Core Principles
- Author-first, not debug-first.
- Narrative knowledge base, not JSON inspection panel.
- Obsidian/Quartz-inspired, but TextifAI-native.
- Markdown/wiki is central substrate.
- VaERL stays source of truth.
- Status/review stays visible.
- AI tools stay grounded in VaERL, notes, chapters, and evidence.
- Progressive disclosure: author views first, debug artifacts secondary.
- No raw JSON as primary UX.
- Clear CTAs, empty states, and visual hierarchy.
- Accessibility basics: readable contrast, keyboard focus, sensible labels.

## MVP Acceptance Criteria

### Dashboard
- Shows ingestion status.
- Shows chapter status.
- Shows review/retry counts.
- Shows graph summary.
- Shows next actions.

### Graph
- Node size by degree.
- Collision/no-overlap target.
- Filters by kind/tag/chapter/status.
- Local graph view.
- Readable labels.
- Selected node panel visible.

### Wiki
- Materialized Markdown notes.
- Backlinks.
- Tags.
- Search.
- Note preview.

### Node Detail
- Aliases.
- Facts.
- Relationships.
- Source/evidence pointers.
- Review status.
- Edit affordance.

### Editor / AI Suite
- Chapter editor.
- Line/paragraph tools.
- Character Lab.
- Grounded query.

## Language Principles
- Author-facing wording first.
- Internal terms stay secondary or hidden.
- Review actions state impact clearly.
- Retry only for real technical retry cases.

## Layout Direction
- Dashboard and wiki should feel calm and legible.
- Graph should be navigable before decorative.
- Detail panel should summarize before dumping.
- Debug artifacts belong behind secondary surfaces.

## Graph Readability Acceptance (SP-093)
- Degree-based radius visible at glance.
- Local graph mode toggles neighborhood focus.
- Kind/status/tag filters reduce noise fast.
- Edge labels readable on medium density graphs.
- Selected node context stays visible while panning.

## Wiki / Browser Acceptance (SP-093)
- Wiki tab exposes Markdown notes as primary knowledge surface.
- Search + kind/tag/status filters work together.
- Backlinks and outgoing links are visible in note detail.
- Frontmatter summary is visible without opening raw artifacts.

## Node Detail Acceptance (SP-093)
- Node panel includes tags, degree, backlink/outgoing counts.
- Markdown note metadata is visible when note exists.
- VaERL fallback appears only when note missing.

## Open Design Dev Usage
- Setup and MCP/Codex snippet: `docs/textifai-open-design-codex-setup.md`.
- Open Design is dev-only tooling; never runtime dependency.

## Design Review Cadence
- Run lightweight checklist every viewer patch.
- Run deep Open Design review every major UI safepoint.
- Carry top 3 visual/UX deltas into next implementation phase.

