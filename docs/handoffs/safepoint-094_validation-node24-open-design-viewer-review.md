# Validation + Node 24 Open Design Runtime + Manual Viewer Review

## Product Reading
TextifAI es plataforma first-party para autores. VaERL sigue como semantic source of truth; Markdown es substrate editable; viewer/wiki/graph/editor son proyecciones author-facing. Si dashboard, graph, wiki y node detail no son navegables, el producto no existe para el autor.

## Scope
- Confirmar validación completa post-SP093.
- Activar Node 24 de forma local/dev-only y reversible.
- Revalidar Open Design install/build/runtime/MCP.
- Levantar viewer sintético para revisión manual.
- Generar reports, tests y handoff SP094.

## Files Changed
- `docs/handoffs/safepoint-094_validation-node24-open-design-viewer-review.md`
- `tests/fixtures/textifai/validation/expected/sp093_full_validation_results_after_sp093.json`
- `tests/fixtures/textifai/validation/expected/sp094_validation_decision_after_sp093.json`
- `tests/fixtures/textifai/design_tooling/expected/node24_dev_environment_after_sp093.json`
- `tests/fixtures/textifai/design_tooling/expected/open_design_runtime_validation_after_sp093.json`
- `tests/fixtures/textifai/design_tooling/expected/open_design_skills_design_systems_validation_after_sp093.json`
- `tests/fixtures/textifai/design_tooling/expected/open_design_codex_mcp_validation_after_sp093.json`
- `tests/fixtures/textifai/design_tooling/expected/open_design_live_textifai_review_after_sp093.json`
- `tests/fixtures/textifai/design_tooling/expected/open_design_node24_decision_after_sp093.json`
- `tests/fixtures/textifai/viewer_wiring/expected/viewer_markdown_wiki_manual_review_after_sp093.json`
- `tests/fixtures/textifai/viewer_wiring/expected/viewer_markdown_wiki_data_quality_after_sp093.json`
- `tests/fixtures/textifai/viewer_wiring/expected/private_viewer_revalidation_status_after_sp093.json`
- `tests/fixtures/textifai/viewer_wiring/expected/viewer_manual_review_decision_after_sp093.json`
- `tests/test_textifai_sp094_validation.py`
- `tests/test_textifai_open_design_node24.py`

## SP093 Context
SP-093 dejó viewer/wiki usable en MVP y Open Design instalado parcialmente, pero sin runtime live por Node 22. SP-094 cierra validación completa, activa Node 24 dev-only con `nvm`, reintenta runtime Open Design y vuelve a levantar viewer para revisión manual.

## Full Validation Results
Se ejecutaron 16 suites base pedidas por SP-093 y todas pasaron. Report commit-safe: `tests/fixtures/textifai/validation/expected/sp093_full_validation_results_after_sp093.json`.

## Node 24 Dev Environment
`nvm` estaba disponible. Se ejecutó `source ~/.nvm/nvm.sh && nvm install 24 && nvm use 24`. Resultado: `v24.16.0` usable en shell local. Rollback: volver a `nvm use 22` o cerrar shell. Sin cambio global irreversible.

## Open Design Runtime / Daemon Validation
- Clone externo: `/tmp/textifai_dev_tools/open-design`
- Install: OK bajo Node 24.
- Build daemon CLI: OK.
- `od mcp --help`: OK.
- `tools-dev start web`: bloqueado por `ENOTSUP` pipe/socket en este entorno.
- Daemon CLI directo: llegó a loguear `listening`, pero endpoint no quedó estable para check HTTP.
Resultado: Open Design usable parcialmente como tooling dev (install/build/MCP/help), pero runtime web live sigue inestable en este entorno.

## Open Design Skills / Design Systems Validation
Conteos validados desde repo Open Design:
- skills: 132
- design systems: 150
Recomendados para TextifAI:
- `design-review`
- `plan-design-review`
- `web-design-guidelines`
- `d3-visualization`
- `design-consultation`
Design system base recomendado: `dashboard`.

## Open Design Codex/MCP Validation
`docs/textifai-open-design-codex-setup.md` sigue vigente. Snippet MCP manual presente. Config global Codex no tocada. Riesgo principal: runtime daemon no estable en este entorno y restart del cliente MCP tras reinicio del daemon.

## Open Design Live TextifAI Review
No hubo flujo live completo de Open Design sobre proyecto real desde CLI. Sí hubo:
- runtime/build validation real bajo Node 24;
- review privado/manual commit-safe+private apoyado en docs/checklist y outputs de validación.
Private output: `/tmp/textifai_private_provider_runs/sp094_validation_node24_open_design_viewer/20260526T175334Z/open_design_outputs/textifai_design_review_live.md`

## Viewer Manual Review Server
Viewer sintético levantado en `http://127.0.0.1:8871` con root `tests/fixtures/textifai/viewer_wiring/input` y host `0.0.0.0`. Endpoints `/`, `/api/projects`, `/api/projects/<id>`, `/api/projects/<id>/graph`, `/api/projects/<id>/note` respondieron 200.

## Viewer Data Quality Check
Proyecto sintético confirmó:
- overview author-facing OK;
- wiki notes disponibles;
- note detail con frontmatter/tags/backlinks/outgoing/local graph;
- graph con degree y edges esperadas;
- artifacts/debug sigue secundario.
Readiness: `ready_for_manual_author_review_with_minor_ui_warnings`.

## Optional Private Viewer Revalidation
No se usaron datos privados reales en SP-094. Solo proyecto sintético commiteable. Private handoff existe solo para Open Design/output notes y dejar rastro de decisión.

## Commit-safe vs Private Decision Handoff
Commit-safe:
- `docs/handoffs/safepoint-094_validation-node24-open-design-viewer-review.md`
Private:
- `/tmp/textifai_private_provider_runs/sp094_validation_node24_open_design_viewer/20260526T175334Z/decision_handoff_private.md`
- `/tmp/textifai_private_provider_runs/sp094_validation_node24_open_design_viewer/20260526T175334Z/open_design_outputs/textifai_design_review_live.md`

## Product Decision
`validation_open_design_ready_viewer_needs_review`

## Recommended Next Phase
Phase 1.3.M-b5c-4x — Spanish 20-chapter E2E preflight + manual viewer review signoff.

## What Worked
- Node 24 activado dev-only con `nvm`.
- Validación completa post-SP093 en verde.
- Open Design install/build/MCP/help validados.
- Viewer sintético manual review server levantado y endpoints OK.

## What Failed
- `tools-dev` Open Design sigue bloqueado por `ENOTSUP` pipe/socket en este entorno.
- Daemon CLI directo no quedó estable para endpoint live continuo.
- No se ejecutó workflow full live de Open Design sobre viewer.

## Data Written
- Reports commit-safe SP094.
- Tests nuevos SP094.
- Handoff SP094.
- Private notes en `/tmp`.

## Privacy / Non-committed Output
No provider calls. No OpenAI. No DeepSeek. No retry. No full-source. No write-back. No repo Open Design commit. No outputs privados commit.

## Tests Added / Updated
- `tests/test_textifai_sp094_validation.py`
- `tests/test_textifai_open_design_node24.py`

## Validation Performed
- Suites SP094 nuevas.
- Batería completa requerida por usuario.
- Viewer endpoint checks en `8871`.
- Open Design Node 24 install/build/runtime attempt.

## Safety Constraints
Node 24 activado solo en shell local con `nvm`. Sin cambios a `package.json`/`package-lock.json` de TextifAI. Open Design sigue dev-only.

## Known Limitations
- Open Design runtime web no estable en este entorno.
- Viewer sigue read-only.
- Manual visual review por usuario sigue necesaria antes del E2E español.

## Future Extensions
- Resolver runtime Open Design live estable en este entorno.
- Ejecutar review visual real con Open Design sobre shell viewer.
- Añadir editor Markdown + patch proposal queue.

## Runtime Changes
Viewer sintético SP094 queda listo para revisión manual en `8871`. Node 24 disponible via `nvm` para futuros comandos dev-only.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
