# SP-121C handoff — graph/canon node fiche editor surface

## Final status
- SP-121C closed: visual fiche editor surface active in Graph/Canon inspector.
- Wikilink-friendly fiche behavior present in generated relationship lines (`[[Label]]`).
- Fiche remains local-only and no writeback path is enabled.

## Scope
- Replace raw node fiche textarea with embedded MDX visual editor surface.
- Add pretty fiche markdown shaping with wikilink relationship lines.
- Keep local-only edits (no writeback).
- Keep technical markdown hidden by default in collapsed technical details.

## Delivered
- Embedded MDX editor in node fiche section (`EntityFicheView`).
- Removed visible markdown mode pill from node fiche section.
- Local edit notice reduced to subtle i18n note.
- Generated fiche markdown builder now normalizes weak source body:
  - title + summary
  - aliases
  - relationships
  - evidence/references
  - notes
- Relationship lines emitted with wikilink syntax (`[[Label]]`) for navigation-ready semantics.
- Added i18n keys for generated fiche sections and fallback labels.

## No-writeback guarantees
- writeback_enabled=false
- no ProjectStore mutation
- no VaERL mutation
- no graph/review regeneration
- no provider calls

## Validation
- `uv run python scripts/dev/textifai_doctor.py` ✅
- `uv run python -m unittest -v tests.test_textifai_graph_fiche_editor_surface` ✅
- `uv run python -m unittest -v tests.test_textifai_i18n_ui_strings` ✅
- `uv run python -m unittest -v tests.test_textifai_mdxeditor_spike` ✅
- `cd textifai/web_viewer/react_shell && npm run build` ✅
- viewer runtime `8872` HTTP 200 ✅

## Visual verification
- Ren: `/tmp/sp121c-ren-fiche.png` ✅
- Magia: `/tmp/sp121c-magia-fiche.png` ✅
- Sera: `/tmp/sp121c-sera-fiche.png` (node not found by url preselect in current graph payload)

Observed on verified nodes:
- fiche switches with selected node
- fiche section uses visual MDX surface (not textarea)
- no visible markdown mode pill in node fiche
- raw markdown/debug not visible by default
- local edit copy subtle and honest
- wikilink-friendly generated markdown present in editor body

## Remaining blockers before writeback
- node-select by URL for all labels still data-dependent (e.g., Sera missing in current runtime snapshot)
- full click-through wikilink navigation not yet implemented (text preserved only)
- writeback pipeline intentionally out-of-scope

- Canon wiki reuse pending
- entity fiche ProjectStore write-back pending
- SP-119B visual tooling / Playwright baseline cleanup pending if verification tooling is retained long-term

## Assessment
- `graph_fiche_visual_editor_surface_ready`
