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
