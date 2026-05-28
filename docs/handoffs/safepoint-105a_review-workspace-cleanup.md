# Review Queue + Workspace UX Cleanup

## Product Reading
TextifAI es plataforma first-party para autores. VaERL sigue semantic source of truth y Markdown sigue substrate editable author-facing. Esta fase convierte Revisión en cola editorial entendible y limpia framing de producto hacia Workspace.

## Scope
- SP-105A implementado en frontend product-facing y contracts/reporting.
- Sin provider calls, sin write-back, sin package changes.
- Sin heurísticas de merge reales (queda para SP-105B).

## Files Changed
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/index.html`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_review_workspace_cleanup.py`
- `tests/test_textifai_product_ux_architecture.py`
- `tests/fixtures/textifai/review_workspace_cleanup/expected/*.json`

## SP104 Context
SP-104 separó Product/Dev, mejoró Overview y Canon, y creó `navigateToGraphNode(...)`. SP-105A se apoya en eso para convertir Review a UX de decisión editorial.

## Open Design Status
- MCP `open-design` registrado y usable en sesión.
- Daemon healthy en `http://127.0.0.1:7457/api/health`.
- Lazyweb MCP usable para referencias de decisión estilo Linear/Notion.
- Open Design usado como tooling de guía (compose brief), no como dependencia runtime.

## ReviewDecisionItem View Model
Se introdujo builder frontend-derived `ReviewDecisionItem`:
- `buildReviewDecisionItems(rawReviewItems, context)`
- `buildReviewDecisionItem(item, index, context)`
Campos: id, title, plain_language_issue, why_it_matters, evidence_summary, affected_entities, affected_chapters, recommendation, severity_label, decision_type_label, actions, technical_details, raw_type, raw_status.

## Review Queue Author-Facing Cleanup
- Revisión ahora renderiza tarjetas editoriales en lenguaje natural.
- Filtros y orden localizados para autor.
- Desaparece framing principal de raw grouped entries y candidate drilldown técnico.
- Se oculta `not available` en superficie primaria de decisión.

## Review Actions Contract
Acciones product-facing:
- Ver evidencia
- Abrir entidad origen
- Abrir entidad relacionada
- Ver relación en el grafo
- Ver ficha en Canon / Entidades
- Marcar como correcto (disabled)
- Marcar como falso positivo (disabled)
- Dejar para más tarde (disabled)

Acciones con persistencia quedan deshabilitadas con explicación de fase.

## Product vs Dev Details in Review
- Product: issue, impacto, evidencia, entidades afectadas, recomendación, acciones.
- Dev/details: raw_type, raw_status, metadata y conteos técnicos en `<details>` colapsado.

## Naming / Viewer Cleanup
Copy visible actualizado de Viewer a Workspace:
- `TextifAI Author Workspace`
- `Mis obras`
- `Abrir proyecto`
- `Workspace local-first`

Se mantiene `web_viewer` y `viewer_project` en internals/compat.

## Open Project / Workspace Flow
Producto:
- Mis obras → Abrir proyecto → Workspace narrativo.

Seguridad local-dev:
- Lista basada en roots registrados/servidos.
- Sin filesystem browser arbitrario en Product Mode.

## SaaS-ready Layer Boundaries
- Introducido `WorkspaceSummary` frontend-derived para tarjetas de proyecto.
- Introducido `ReviewDecisionItem` para Review product-facing.
- Product consume view-models author-facing; Dev conserva diagnostics/raw.

## Stable Author Workspace on 8872
Validado runtime estable en `8872` con endpoints:
- `/`
- `/api/projects`
- `/api/projects/<id>`
- `/api/projects/<id>/graph`
- `/api/projects/<id>/note?path=Characters/Sera.md`

## Private Decision Handoff
Private output generado (no commit):
- `docs/handoffs/private/safepoint-105a_review-workspace-cleanup/decision_handoff_private.md`

## Product Decision
`review_workspace_cleanup_ready_for_manual_review`

## Recommended Next Phase
SP-105B: generación real de merge candidates (abuelo/Sera variants) sobre esta cola editorial ya limpia.

## What Worked
- ReviewDecisionItem permitió separar raw vs product copy.
- Reuso de `navigateToGraphNode` funcionó para acciones de Review.
- Naming cleanup visible sin romper rutas internas.

## What Failed
- No se implementó persistencia de decisiones (fuera de scope).
- `app.js` sigue monolítico; separación completa queda pendiente.

## Data Written
- Reports JSON SP-105A en `tests/fixtures/textifai/review_workspace_cleanup/expected/`.
- Test suite SP-105A nueva.
- Handoff público y handoff privado.

## Privacy / Non-committed Output
No se commitea:
- `docs/handoffs/private/safepoint-105a_review-workspace-cleanup/decision_handoff_private.md`
- `/tmp/**`
- outputs privados/provider.

## Tests Added / Updated
- Added: `tests/test_textifai_review_workspace_cleanup.py`
- Updated: `tests/test_textifai_product_ux_architecture.py`

## Validation Performed
- Unit tests SP-105A + regresión SP-104 y suites requeridas.
- Endpoint checks `8872` completados.

## Safety Constraints
- provider calls: NO
- package changes: NO
- write-back: NO
- graph engine changes: NO

## Known Limitations
- Persistencia de decisiones de revisión aún no implementada.
- Merge candidate generation real diferida a SP-105B.

## Future Extensions
- SP-105B: merge suggestions reales + casos abuelo/Sera.
- SP-106: drafts Markdown + diff + patch queue.
- SP-107: apply patch a VaERL y feedback loop.

## Runtime Changes
Ninguna dependencia runtime nueva; solo ajustes UI/UX y contratos frontend-derived.

## Write-back
No write-back ejecutado.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
