# Node Selection + Inspector Hydration Fix

## Product Reading
TextifAI es plataforma first-party para autores. VaERL es semantic source of truth. Markdown es substrate editable author-facing. Viewer/wiki/graph/node detail sostienen flujo diario del autor: seleccionar nodo, leer ficha, decidir narrativa.

## Scope
SP-102 corrige bug bloqueante de selección de nodo en grafo y fortalece fallback de inspector sin cambiar motor, dependencias o pipeline.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `tests/test_textifai_author_workspace_stabilization.py`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/node_selection_click_drag_audit_after_sp101.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/inspector_hydration_fallback_after_sp101.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/sera_ren_node_selection_after_sp101.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/node_selection_inspector_decision_after_sp101.json`

## SP101 Context
SP-101 dejó grafo usable, i18n español y canonical kind/filter listos. Persistía bug: click nodo no abría ficha; inspector quedaba en “Selecciona un nodo para revisar.”

## Click vs Drag Root Cause
`bindNodeDrag()` marcaba `state.graphDidDragNode = true` en cualquier `pointermove`. Handler de click cortaba temprano y evitaba `selectGraphNode()`.

## Drag Threshold Fix
- Se añade `GRAPH_CLICK_DRAG_THRESHOLD_PX = 5`.
- `pointerdown` guarda `startX/startY`.
- `pointermove` calcula `Math.hypot(deltaX, deltaY)`.
- Solo si distancia supera umbral se marca drag y se mueve nodo.
- Micro-movimiento preserva click normal.

## Canonical Selection Flow
Flujo reforzado:
click visible node -> `resolveCanonicalNodeId` -> `selectGraphNode(canonicalId)` -> `state.selectedGraphNodeId` actualizado -> `renderGraphNodeDetail` -> `canonical_note_path` preferido sobre `note_path`.

## Inspector Hydration Fallback
- `renderGraphNodeDetail()` ahora muestra estado `Cargando ficha...` al seleccionar.
- Si carga de nota canónica falla, renderiza fallback local con hydration del nodo:
  - `summary_excerpt`
  - `key_facts_preview`
  - `relationship_count`
  - `evidence_count`
- Aviso discreto: “No se pudo cargar la nota completa. Mostrando resumen disponible.”
- Se corrige orden interno en `openGraphNote()` para no referenciar `summaryNode` antes de definirlo.

## Sera/Ren Manual Review Targets
- Sera: click debe resolver a `Characters/Sera.md`.
- Ren: click debe resolver a `Characters/Ren.md`.
- Duplicados concept redirigidos no deben secuestrar inspector.

## Stable Author Workspace on 8872
Runtime mantenido en `8872` sobre:
`/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch/20260527T124326Z`

Endpoints verificados: `/`, `/api/projects`, `/api/projects/<id>`, `/api/projects/<id>/graph`, `/api/projects/<id>/note?path=Characters/Sera.md`, `/api/projects/<id>/note?path=Characters/Ren.md`.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-102_node-selection-inspector-hydration/decision_handoff_private.md`

## Product Decision
node_selection_inspector_hydration_ready_for_manual_review

## Recommended Next Phase
Validación manual fina de interacción click/drag en distintos dispositivos y ajuste de micro-copy secundaria fuera de flujo primario.

## What Worked
Fix puntual en interacción preservando d3-force, selección canónica intacta, fallback hydration útil sin provider.

## What Failed
Sin screenshots/browser automation, validación visual se limita a endpoints + tests estáticos.

## Data Written
Se escriben 4 reports SP-102 commit-safe y handoff público. Handoff privado en ruta gitignored.

## Privacy / Non-committed Output
No stage de `docs/handoffs/private/**`, `.codegraph/`, `.superpowers/`, `/tmp/**`, `node_modules/`, `.env*`.

## Tests Added / Updated
- `tests/test_textifai_author_workspace_stabilization.py` (cobertura SP-102 click/drag, canonical selection, hydration fallback, reports SP-102).

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_author_workspace_stabilization`
- `uv run python -m unittest -v tests.test_textifai_author_workspace_redesign`
- `uv run python -m unittest -v tests.test_textifai_open_design_viewer_review`
- `uv run python -m unittest -v tests.test_textifai_author_facing_viewer_ux`
- `uv run python -m unittest -v tests.test_textifai_viewer_graph_architecture`
- `uv run python -m unittest -v tests.test_textifai_vaerl_entity_quality_and_viewer_ux_patch`
- `uv run python -m unittest -v tests.test_textifai_spanish_20ch_e2e_preflight`
- `uv run python -m unittest -v tests.test_textifai_viewer_markdown_wiring`
- `uv run python -m unittest -v tests.test_textifai_markdown_materialization`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- endpoint checks 8872

## Safety Constraints
Provider calls: NO. Package changes: NO. Graph engine change: NO. Write-back: NO. Browser automation: NO. Screenshots: NO.

## Known Limitations
No editor Markdown, no patch queue, no enrichment LLM, no ingest nueva en SP-102.

## Future Extensions
Afinar comportamiento de selección para touch/pen y añadir cobertura de interacción end-to-end UI (cuando se habilite harness de navegador).

## Runtime Changes
Sin cambios de dependencias ni motor. Solo lógica interacción/inspector frontend.

## Write-back
No.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
