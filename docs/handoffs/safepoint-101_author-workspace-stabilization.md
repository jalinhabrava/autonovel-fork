# Author Workspace Stabilization

## Product Reading
TextifAI es plataforma first-party para autores. VaERL es semantic source of truth. Markdown es substrate editable author-facing. Viewer/wiki/graph/node detail son superficies centrales del producto y deben comportarse como producto estable, no como debug UI.

## Scope
SP-101 estabiliza runtime y UX base sin rediseño nuevo: fix sidebar load, locale español robusto, canonical kind para filtro/render, default author graph scope, y hydration ligera de contenido de nodo desde Markdown existente.

## Files Changed
- `textifai/web_viewer/static/index.html`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/project_reader.py`
- `tests/test_textifai_author_workspace_stabilization.py`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/sidebar_project_load_audit_after_sp100.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/spanish_i18n_runtime_audit_after_sp100.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/canonical_graph_kind_filter_audit_after_sp100.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/default_author_graph_scope_after_sp100.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/graph_v3_density_layout_audit_after_sp100.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/node_content_hydration_audit_after_sp100.json`
- `tests/fixtures/textifai/author_workspace_stabilization/expected/author_workspace_stabilization_decision_after_sp100.json`

## SP100 Context
SP-100 mejoró shell y d3-force, pero dejó bug bloqueante de carga de proyectos, locale inconsistente tras `selectProject`, canonical kind incompleto para graph/filter y sobrecarga de ruido inicial.

## Sidebar Project Load Fix
Root cause: `renderOverview()` llamaba `projectTitle(...)` sin helper definido. Se añade helper robusto `projectTitle(project, current)` con fallback seguro. Carga de proyectos deja de romper con `projectTitle is not defined`.

## Spanish i18n Runtime Fix
Backend `read_project()` ahora expone `project.work` completo. Frontend `detectLocale()` evalúa: `project.work` -> `canon.work` -> summary `work` -> `navigator.language` -> `en`. Runtime español queda en `es` tras `selectProject`, no vuelve a inglés por ausencia de `work`.

## Canonical Graph Kind / Filter Fix
Backend añade campos de representación canónica por nodo: `canonical_kind`, `display_kind`, `canonical_degree`, más `canonical_node_id`/`canonical_note_path`. Frontend usa `display_kind/canonical_kind` para filtro. Duplicados redirigidos se colapsan por defecto. Sera/Ren se comportan como character en graph/filter/inspector.

## Default Author Graph Scope
Default scope pasa a vista author-friendly y deja full graph detrás de toggle `Mostrar todo`:
- oculta `chapter/review/system` por defecto;
- colapsa duplicados redirigidos;
- muestra `character/place/object/event` con degree >= 2;
- muestra `concept` solo si no redirigido y degree >= 8.
Resultado actual: 67 nodos default (target 40–80) vs 446 full.

## Graph v3 Density / Layout Stabilization
Se mantiene GraphEngine v3 con `d3-force`. Densidad se corrige por scope (no cambio de motor). Se conserva simulación, colisión y re-render al cambiar scope; labels de edge siguen ocultas por defecto y labels de nodo siguen política adaptativa.

## Node Content Hydration
Se añade extracción ligera provider-free desde Markdown canónico:
- `summary_excerpt`
- `key_facts_count`
- `key_facts_preview`
- `relationship_count`
- `evidence_count`
Incluido en payload graph y `read_note.content_hydration`. Inspector puede mostrar fallback útil incluso antes de detalle completo.

## Stable Author Workspace on 8872
Servidor estable relanzado con launcher en `8872`. Runtime servido: `/tmp/textifai_private_provider_runs/sp096_vaerl_entity_quality_viewer_ux_patch/20260527T124326Z`. Endpoints `/`, `/api/projects`, `/api/projects/<id>`, `/api/projects/<id>/graph`, `/api/projects/<id>/note` validados.

## Private Decision Handoff
- `docs/handoffs/private/safepoint-101_author-workspace-stabilization/decision_handoff_private.md`

## Product Decision
author_workspace_stabilization_ready_for_manual_review

## Recommended Next Phase
SP-102: consolidar traducción de superficies secundarias review/dev, añadir presets de scope author avanzados, y refinar acciones de inspector/review sin write-back.

## What Worked
Fix de carga sidebar, locale español persistente, canonical kind operativo, reducción de ruido inicial con scope default, hydration ligera útil sin provider.

## What Failed
Quedan strings secundarios en inglés en flujos review/dev no críticos. Full graph sigue denso por diseño cuando `Mostrar todo` está activo.

## Data Written
Reports commit-safe SP-101 y handoff público. Handoff privado creado en ruta gitignored.

## Privacy / Non-committed Output
No stage de `docs/handoffs/private/**`, `.codegraph/`, `.superpowers/`, `/tmp/**`, `node_modules/`, outputs privados o runtime privado.

## Tests Added / Updated
- `tests/test_textifai_author_workspace_stabilization.py`

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
- endpoint checks `8872`

## Safety Constraints
Provider calls: NO. Package changes: NO. Graph engine change: NO. Write-back: NO. Browser automation: NO. Screenshots: NO.

## Known Limitations
No editor Markdown. No patch proposal queue. No LLM enrichment. No nueva ingestión en esta fase.

## Future Extensions
Mejorar cobertura i18n en módulos de revisión/dev, presets scope por modo autor/editor, y refinamiento de señales visuales en graph local/global.

## Runtime Changes
Sin cambios de dependencia. Viewer en 8872 con mismas bases SP-100 + fixes de estabilización SP-101.

## Write-back
No.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
