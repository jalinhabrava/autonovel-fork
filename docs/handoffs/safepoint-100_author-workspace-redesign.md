# Author Workspace Redesign + d3-force GraphEngine v3

## Product Reading
TextifAI es plataforma first-party para autores. VaERL es semantic source of truth. Markdown es substrate editable author-facing. Viewer/wiki/graph/node detail son superficies centrales del producto, no debug UI.

## Scope
Rediseño de shell author workspace, drawer Dev, GraphEngine v3 con `d3-force`, inspector narrativo, dashboard/wiki/review author-facing, i18n primaria, reports y validación final.

## Files Changed
- `package.json`
- `package-lock.json`
- `textifai/web_viewer/static/index.html`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `textifai/web_viewer/static/vendor/d3-force.bundle.min.js`
- `tests/test_textifai_author_workspace_redesign.py`
- `tests/fixtures/textifai/author_workspace_redesign/expected/open_design_mcp_verification_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/package_impact_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/author_workspace_shell_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/d3_force_graph_engine_v3_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/graph_v3_ux_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/node_inspector_author_card_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/dashboard_author_home_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/wiki_kb_redesign_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/review_queue_author_decisions_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/i18n_primary_ux_coverage_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/stable_author_workspace_8872_after_sp099.json`
- `tests/fixtures/textifai/author_workspace_redesign/expected/author_workspace_redesign_decision_after_sp099.json`

## SP099 Context
SP-099 dejó Open Design operativo como tooling dev y aprobó `d3-force`. SP-100 toma esa dirección y deja de parchear viewer incrementalmente para moverlo a author workspace real.

## Open Design MCP Verification
`open-design` queda registrado en Codex. Daemon healthy en `http://127.0.0.1:7457/api/health`. Se usó como guía de diseño dev-only, sin dependencia runtime en TextifAI.

## Package Strategy
Se limpió package metadata histórico no trackeado. `map` no se usa en repo. Se creó package mínimo intencional del viewer y se añadió solo `d3-force`. Runtime estático usa bundle vendorizado en `textifai/web_viewer/static/vendor/d3-force.bundle.min.js`.

## Author Workspace Shell
`viewer_project` queda como workspace autor por defecto. `markdown_vault` baja a artifact técnico secundario dentro de drawer Dev. Navegación primaria: Resumen, Wiki, Canon, Revisión, Grafo, Dev.

## d3-force GraphEngine v3
Se conserva Graph Contract v2 y renderer SVG. `edge.id` sigue siendo identidad única. Fuerzas activas: `forceSimulation`, `forceCenter`, `forceManyBody`, `forceLink`, `forceCollide`, `forceX`, `forceY`. Drag/pin/reset/local graph quedan sobre visible graph único.

## Graph UX v3
Se reduce efecto rail con seeded radial layout + simulación física. Fit con padding. Characters y nodos high-degree sesgados al centro. Labels de edges quedan ocultas por defecto y aparecen solo en hover/detalle.

## Node Inspector Author Card
Panel derecho ordenado para autor: resumen, facts, relaciones narrativas, evidencia, backlinks y detalles técnicos colapsados. Redirect duplicado queda dentro de detalles técnicos.

## Dashboard Author Home
Resumen narrativo con story health, capítulos procesados, revisión, retry, graph health y siguiente acción. CTA primaria abre Wiki o Grafo.

## Wiki KB Redesign
Wiki queda como knowledge base narrativa de solo lectura, con filtros y detalle orientado a canon y backlinks, no a inspección de filesystem.

## Review Queue Author Decisions
Revisión se presenta como cola de decisiones. Se reduce tono de audit dump y se orienta cada item a issue, evidencia y siguiente acción.

## i18n Primary UX
Primary UX pasa por dictionary `en/es`. Runtime español cae a `es`. Se elimina mezcla visible en navegación y superficies principales.

## Stable Author Workspace on 8872
`8872` sigue sirviendo SP-096, no SP-095. Proyecto manual de revisión: `tmp__textifai_private_provider_runs__sp096_vaerl_entity_quality_viewer_ux_patch__20260527T124326Z__viewer_project`. URL: `http://127.0.0.1:8872/`.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-100_author-workspace-redesign/decision_handoff_private.md`

## Product Decision
author_workspace_redesign_ready_for_manual_review

## Recommended Next Phase
SP-101: editor entry points, markdown edit affordances, richer inspector actions, y mejor hydration de summary/facts dentro de payload graph.

## What Worked
Package cleanup intencional, separación Dev drawer, carga de `d3-force`, edge identity estable, runtime 8872 estable, canonical note opening para inspector.

## What Failed
No hubo revisión visual automática por screenshot. Payload graph aún no hidrata summary/facts ricos inline; inspector depende de fetch de nota canónica.

## Data Written
Reports JSON commit-safe, handoff público, handoff privado gitignored.

## Privacy / Non-committed Output
Fuera de stage: `docs/handoffs/private/**`, `node_modules/`, `/tmp/**`, Open Design repo, config Codex, outputs privados.

## Tests Added / Updated
- `tests/test_textifai_author_workspace_redesign.py`

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_author_workspace_redesign`
- `uv run python -m unittest -v tests.test_textifai_open_design_viewer_review`
- `uv run python -m unittest -v tests.test_textifai_author_facing_viewer_ux`
- `uv run python -m unittest -v tests.test_textifai_viewer_graph_architecture`
- `uv run python -m unittest -v tests.test_textifai_vaerl_entity_quality_and_viewer_ux_patch`
- `uv run python -m unittest -v tests.test_textifai_spanish_20ch_e2e_preflight`
- `uv run python -m unittest -v tests.test_textifai_viewer_markdown_wiring`
- `uv run python -m unittest -v tests.test_textifai_markdown_materialization`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- checks endpoint `8872`
- `git status --short`
- `git diff --stat`

## Safety Constraints
Provider calls: NO. Write-back: NO. Browser automation: NO. Screenshots: NO. Open Design runtime dependency: NO.

## Known Limitations
No editor Markdown todavía. No patch queue. No hydration inline completa de summary/facts en payload graph. Bundle d3 queda vendorizado porque no hay bundler frontend.

## Future Extensions
Editor entry points, zoom semantics, clusters, richer inspector actions, review queue más accionable, payload graph más rico.

## Runtime Changes
Viewer estático ahora carga `d3-force` desde vendor bundle. Puerto fijo `8872` se mantiene.

## Write-back
No.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
