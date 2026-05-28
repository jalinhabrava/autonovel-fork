# Product Mode vs Dev Mode: Overview + Canon/Entities

## Product Reading
TextifAI es plataforma first-party para autores. VaERL manda como semantic source of truth. Markdown sigue siendo substrate editable author-facing. SP-104 separa UX de producto de tripería técnica.

## Scope
Separación product/dev, rediseño de Resumen, Canon / Entidades clicable, contrato Ver en grafo, tono más author-facing en Revisión, reports/tests/handoff.

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/index.html`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_product_ux_architecture.py`
- `tests/fixtures/textifai/product_ux_architecture/expected/product_vs_dev_mode_audit_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/overview_redesign_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/dev_debug_surface_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/canon_entities_redesign_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/view_in_graph_contract_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/canon_rows_selection_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/review_queue_product_tone_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/merge_canonicalization_workflow_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/editable_markdown_workflow_after_sp102.json`
- `tests/fixtures/textifai/product_ux_architecture/expected/product_ux_architecture_decision_after_sp102.json`

## SP102 Context
SP-102 dejó click/drag/inspector estables. Persistía deuda grande de arquitectura UX: producto vs debug mezclados.

## Working Tree Local Changes Handling
Se inspeccionaron cambios locales no committeados en `app.js`, `index.html`, `styles.css`, `tests/test_textifai_author_workspace_stabilization.py`. Clasificación: browser-native UX edits coherentes con SP-104. Se conservaron e integraron: sidebar footer fijo, layout con scroll en workspace, filtros wiki limpios, tab Canon author-facing, ajustes de inspector y responsive.

## Product Mode vs Dev Mode
Resumen, Grafo, Wiki, Canon / Entidades y Revisión quedan author-facing. Dev concentra semantic health, compare runs, triage, ingestion, raw artifacts y canonicalization internals.

## Overview Redesign
Resumen ahora muestra estado de obra, siguiente acción, decisiones pendientes, entidades principales y estado del grafo en lenguaje natural. Se quitan paneles técnicos del flujo primario.

## Dev Debug Surface
Dev pasa a ser superficie explícita. Agrupa diagnósticos técnicos y artefactos sin contaminar Resumen o Canon.

## Canon / Entities Redesign
Canon pasa a `Canon / Entidades`. Filas clicables, panel lateral narrativo, acciones reales de navegación y placeholders honestos para SP-105.

## Canon Row Selection
Seleccionar fila actualiza entidad activa, resalta fila y sincroniza acciones del panel lateral.

## View in Graph Contract
Nuevo helper central `navigateToGraphNode(...)`: resuelve canonical id, revela nodo si estaba oculto, cambia a Grafo, centra, selecciona y abre inspector.

## Review Queue Product Tone
Revisión cambia cabecera y resumen a tono de cola de decisiones. Internals crudos quedan en Dev o en raw artifact explícito.

## Merge / Canonicalization Workflow Contract
Se deja contrato UI para SP-105: alias exactos, aliases descriptivos, overlap relacional, evidencia por capítulo y selección manual. Sin heurísticas fuertes todavía.

## Editable Markdown Workflow Contract
Se deja contrato para SP-106: editar ficha -> draft local -> diff -> pendiente de aplicar al canon. Sin write-back.

## Stable Author Workspace on 8872
Se recreó runtime privado mínimo en `/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch/20260527T124326Z/viewer_project` para sostener tests y server estable en `8872`.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-104_product-dev-mode-overview-canon/decision_handoff_private.md`

## Product Decision
`product_dev_mode_separation_ready_for_manual_review`

## Recommended Next Phase
SP-105: merge candidates y canonicalization contextual con casos abuelo/Sera.

## What Worked
Separación product/dev clara, overview útil, canon seleccionable, helper central de navegación, runtime mínimo reproducible en `/tmp`.

## What Failed
No se implementan merge heuristics reales. Wiki detail sigue más técnica de lo ideal. Runtime SP-096 original no estaba presente y hubo que recrear fixture privada mínima.

## Data Written
Reports commit-safe SP-104, handoff público SP-104, runtime privado mínimo en `/tmp`, handoff privado gitignored.

## Privacy / Non-committed Output
No stage de `docs/handoffs/private/**`, `/tmp/**`, `.codegraph/`, `.superpowers/`, provider outputs, `.env*`.

## Tests Added / Updated
Nuevo `tests/test_textifai_product_ux_architecture.py`.

## Validation Performed
Node syntax check, tests SP-104, tests SP-101/SP-102 relacionados, runtime checks en `8872`, `git status --short`, `git diff --stat`.

## Safety Constraints
Provider calls: NO. Package changes: NO. Write-back: NO. Graph engine changes: NO.

## Known Limitations
Merge suggestions aún placeholder. Editor Markdown no implementado. Dev surface todavía prioriza estructura sobre polish final.

## Future Extensions
SP-105 merge candidates, SP-106 drafts Markdown, SP-107 apply-to-VaERL.

## Runtime Changes
Runtime privado recreado en `/tmp` para recuperar `viewer_project` expected por tests y revisión manual.

## Write-back
No.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
