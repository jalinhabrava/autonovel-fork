# SP-117 — Editor dirty-state UX + reanalysis entrypoint

## Scope
- Local save-state UX in editor.
- Contextual save banner with fade behavior.
- Semantic pending state ownership in Canon risks card.
- Reanalysis entrypoint added as backend placeholder.

## Two status zones decision
- Zone 1 local save state: title subline + contextual banner.
- Zone 2 semantic state: right panel Canon risks only.
- Removed always-on duplicate explanatory warning text.

## Local save UX
- States: `idle`, `dirty`, `saving`, `saved`, `conflict`, `error`.
- Dirty on edit shows `Cambios sin guardar`.
- Saving shows `Guardando…` and save disabled.
- Success shows `Capítulo guardado. Canon/VaERL pendiente de reanálisis.` and auto-fades.
- Conflict persists with `Conflicto: el capítulo cambió en disco. Recarga antes de guardar.`
- Error persists with `Error al guardar: ...`.

## Contextual banner
- Hidden when no actionable message.
- Visible for dirty/saving/saved/conflict/error.
- Saved auto-hide timeout: 4000ms.

## Canon risks / needs_reanalysis
- Card shows `Pendiente de reanálisis`.
- Copy states no Canon/VaERL, Graph, Review regeneration done.

## Reanalysis placeholder endpoint
- UI action: `Reanalizar capítulo`.
- API: `POST /api/projects/<id>/chapters/<chapter_id>/reanalyze`.
- Current response: `202` + `status: not_implemented`.
- UI does not claim reanalysis completed.

## Runtime smoke
- Viewer HTTP root and project API reachable.
- Edit→save→reanalysis placeholder→hash conflict path exercised.
- No VaERL writeback, Graph regeneration, Review regeneration.

## Tests
- Added `tests/test_textifai_editor_dirty_state_ux.py`.
- Existing SP-115A/SP-113A tests re-run with build verification.

## Non-goals
- No provider calls.
- No mini-ingestion.
- No semantic regeneration.
- No source prose in reports.
