# Stable Viewer Server + Graph Contract v2 + Native Graph Engine v2

## Product Reading
TextifAI es plataforma first-party author-facing: VaERL es semantic source of truth, Markdown es substrate editable, y viewer/wiki/graph/node detail son superficies centrales del producto. El graph debe ayudar al autor a entender canon, relaciones y revisión; no puede depender de runtimes viejos ni de edges visualmente rotos.

## Scope
Provider-free viewer hardening. Sin DeepSeek, sin OpenAI, sin retry, sin full-source, sin write-back, sin screenshots, sin browser automation, sin D3 ni cambios en `package.json`/`package-lock.json`.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/app.js`
- `scripts/dev/textifai_viewer_dev_server.py`
- `tests/test_textifai_viewer_graph_architecture.py`
- `tests/fixtures/textifai/viewer_graph_architecture/expected/*.json`
- `docs/handoffs/safepoint-097_stable-graph-viewer-v2.md`

## SP096 Context
SP-096 corrigió unresolved links, orphan notes, chapter integrity, retry classification, canonical kind preference, drag/nav/legend. ACK posterior detectó que `8872` seguía sirviendo SP-095 y `8873` ya no respondía.

## Server/Port Diagnosis
Diagnóstico inicial confirmó `8872` ocupado por viewer TextifAI SP-095 y `8873` sin listener. El usuario veía assets nuevos del repo combinados con datos viejos SP-095.

## Stable Viewer Server Workflow
Se añadió `scripts/dev/textifai_viewer_dev_server.py` con puerto fijo `8872`, detección de proceso por puerto, rechazo de procesos no TextifAI, kill seguro de viewer TextifAI previo con flag explícito, PID/log en `/tmp`, validación de endpoints y resumen JSON.

## Graph API Contract v2
Backend expone `graph_contract_version: 2`, `edge.id` estable, endpoints edge por `node.id`, `node.radius`, `node.color`, `status/review_state`, `note_path`, `canonical_redirects` y metadata de local graph. Reporte: 446 nodes, 582 edges, 0 bad edges.

## Edge Rendering Fix
Frontend deja de unir lines por índice. SVG usa `data-edge-id`; `updateGraphDom` resuelve por `edge.id`; drag/tick/filter/local graph usan `state.current.visibleGraph` como fuente única.

## Native Graph Engine v2
Se separó lógica interna en funciones: `normalizeGraphData`, `buildVisibleGraph`, `createGraphLayout`, `tickGraph`, `renderGraphDom`, `updateGraphDom`, `bindGraphInteractions`. Renderer sigue siendo SVG custom, sin dependencia externa.

## Graph UX v2
Se mantiene layout force interno con center/repel/link/collision, bias de character/high-degree, radius por degree, labels adaptativos, edge labels contextuales, drag/pin/localStorage, reset layout, legend y navegación interna.

## Quartz / Obsidian Pattern ADR
Se adoptan patrones: global/local graph, degree radius, fuerzas configurables, drag/pin, zoom/pan, labels adaptativos, filtros, recent/internal nav. Se difieren radial graph, D3-force/canvas y rich hover cards. Quartz/Obsidian inspiran UX; no son runtime TextifAI.

## Stable SP096 Viewer on 8872
`8872` sirve SP-096, no SP-095. URL manual: `http://127.0.0.1:8872/`. Project: `tmp__textifai_private_provider_runs__sp096_vaerl_entity_quality_viewer_ux_patch__20260527T124326Z__viewer_project`. Root: `/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch/20260527T124326Z/viewer_project`.

## Private Decision Handoff
Subir a ChatGPT en este orden:
1. `docs/handoffs/private/safepoint-097_stable-graph-viewer-v2/decision_handoff_private.md`
2. `docs/handoffs/private/safepoint-097_stable-graph-viewer-v2/edge_rendering_diagnosis_private.md`
3. `docs/handoffs/private/safepoint-097_stable-graph-viewer-v2/viewer_runtime_private.md`
4. `docs/handoffs/private/safepoint-097_stable-graph-viewer-v2/graph_viewer_v2_quality_private.md`

## Product Decision
`stable_graph_viewer_v2_ready_for_manual_review`

## Recommended Next Phase
Graph Viewer v2 manual UX review, then targeted D3-force ACK or Markdown editor + patch proposal queue depending on user priority.

## What Worked
- Stable server workflow fixed stale runtime confusion.
- Edge identity by `edge.id` removes index mismatch bug.
- Graph Contract v2 gives backend/frontend shared assumptions.
- SP-096 graph serves correctly on fixed port `8872`.

## What Failed
- No visual screenshot/browser automation by constraint.
- SVG custom remains limited versus D3-force/canvas for larger future graphs.

## Data Written
- Commit-safe reports under `tests/fixtures/textifai/viewer_graph_architecture/expected/`.
- Private SP-097 summaries under `docs/handoffs/private/safepoint-097_stable-graph-viewer-v2/`.
- Viewer PID/log under `/tmp/textifai_viewer_8872.*`.

## Privacy / Non-committed Output
Private handoffs and runtime data remain untracked and gitignored. No raw provider outputs, prompts, source prose, API keys, or private packets were staged.

## Tests Added / Updated
- `tests/test_textifai_viewer_graph_architecture.py`

## Validation Performed
- New graph architecture unit suite.
- SP-096, SP-095 preflight, viewer wiring, materialization, SP-094, provider onboarding regressions requested.
- Endpoint checks for `8872` with SP-096 project.

## Safety Constraints
Provider calls: NO. DeepSeek: NO. OpenAI: NO. Retry: NO. Write-back: NO. Screenshots/browser automation: NO. Package dependency changes: NO.

## Known Limitations
Graph Engine v2 is still custom SVG. It fixes identity/contract/server correctness, but D3-force may be better later for richer physics and scale.

## Future Extensions
- ACK for `d3-force` or canvas renderer.
- Layout persistence as review artifact if user wants shared positions.
- Hover cards and edge detail panel.
- Markdown editor + patch proposal queue.

## Runtime Changes
Stable viewer launched on `0.0.0.0:8872` with SP-096 root. PID/log paths: `/tmp/textifai_viewer_8872.pid`, `/tmp/textifai_viewer_8872.log`.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
