# Safepoint 121 — Graph/Canon node fiche editor surface

## Scope
- Reworked Graph inspector into author-facing fiche surface.
- Added reusable fiche body component for future Canon/VaERL reuse.
- Kept edits local-memory only. No persistence/write-back.

## Data source priority
1. `entity-card.markdown.author_markdown`
2. Note markdown body (frontmatter hidden)
3. Generated author-facing markdown (documented for next SP)
4. Empty placeholder

## UI/layout changes
- Compact header with title, entity name, and compact badges.
- Compact metadata grid for aliases, refs, backlinks/outgoing, local graph counts.
- Main fiche body promoted as largest editable area.
- Technical details moved to collapsed accordion.

## Moved/removed behavior
- Old always-open `Vista Markdown` removed from normal surface.
- Raw markdown/json not shown by default.
- Note path moved to compact metadata + technical details.

## Frontmatter handling
- Frontmatter parsed and hidden via shared helper (`stripFrontmatter`).
- Editor body uses markdown body only.

## Technical details policy
- Collapsed by default.
- Includes path and sanitized markdown preview.
- Optional technical markdown shown only inside accordion.

## Local-edit-only limitation
- Fiche body editor is local-only (`textarea`).
- Dirty state copy shown: `Edición local sin guardar.`
- Save-not-available copy shown: `El guardado de fichas llegará en una fase posterior.`

## Runtime verification
- Viewer reachable on `http://127.0.0.1:8872/` (HTTP 200).
- `/api/projects` and `/api/projects/<id>` return 200.
- Real project enumerated and graph payload loaded.
- Codex visual builder skill used: `true`.
- Browser automation opened real project and Graph view.
- Screenshots captured:
  - `/tmp/sp121-visual-real/desktop_graph_default.png`
  - `/tmp/sp121-visual-real/mobile_graph_default.png`
  - `/tmp/sp121-visual-real/desktop_Ren.png`
  - `/tmp/sp121-visual-real/desktop_Magia.png`
  - `/tmp/sp121-visual-real/desktop_Sera.png`
  - `/tmp/sp121-visual-real/mobile_Ren.png`
  - `/tmp/sp121-visual-real/mobile_Magia.png`
  - `/tmp/sp121-visual-real/mobile_Sera.png`
  - `/tmp/sp121-visual-real/proof_Ren.png`
  - `/tmp/sp121-visual-real/proof_Magia.png`
  - `/tmp/sp121-visual-real/proof_Sera.png`
- `browser_visual_pass=true` for closeout gate.
- Reason: deterministic selection proven via visual-test hook query `graph_select` + Graph tab open; inspector `<h2>` resolved exactly to `Ren`, `Magia`, `Sera` and matching screenshots captured.
- `selected_nodes_checked=[Ren, Magia, Sera]` attempted via real browser automation.

## Testability hook
- Added minimal non-UI hook in `textifai/web_viewer/react_shell/src/App.tsx`.
- Query `graph_select=<value>` preselects initial graph node by exact match on `label` / `display_label` / `canonical_id` / `id` during project context load.
- Used only to make visual verification deterministic; no write-back, no provider calls, no ingestion, no new user-facing controls.

## Tests/build
- `uv run python -m unittest -v tests.test_textifai_graph_fiche_editor_surface`
- `uv run python -m unittest -v tests.test_textifai_i18n_ui_strings`
- `uv run python -m unittest -v tests.test_textifai_mdxeditor_spike`
- `cd textifai/web_viewer/react_shell && npm run build`

## Remaining blockers before write-back
- Canon/VaERL shared navigation not yet wired to same component.
- Entity fiche persistence contract through ProjectStore missing.
- Strong canonical-id write path still pending.
- Canon wiki reuse pending.
- ProjectStore entity fiche write-back pending.

## Recommendation for SP-122
- Add ProjectStore entity fiche write-back endpoint + optimistic hash guard.
- Keep same `EntityFicheView` contract; attach save action + conflict banner.
- Reuse source-priority and frontmatter-hide rules unchanged.
