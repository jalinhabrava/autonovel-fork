# Wire VaERL Markdown Wiki/Backlink Index into Viewer MVP + Open Design Skill Setup

## Product Reading
TextifAI es plataforma first-party para autores: VaERL es source of truth, Markdown es substrate editable author-facing, y viewer/wiki/graph/editor son proyecciones útiles sobre VaERL. El viewer debe funcionar como gestor narrativo tipo KB, no como debug viewer ni exportador Obsidian.

## Scope
- Conectar manifest/index Markdown al backend viewer.
- Añadir Wiki/Markdown browser MVP.
- Enriquecer node detail con nota/backlinks/tags/local graph.
- Mejorar graph readability v1.
- Añadir métricas author-facing al overview.
- Instalar/configurar Open Design externo como dev tooling si viable.
- Crear reports, tests, handoff commit-safe.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/index.html`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `docs/textifai-design-direction.md`
- `docs/textifai-ui-review-checklist.md`
- `docs/textifai-open-design-codex-setup.md`
- `tests/test_textifai_viewer_markdown_wiring.py`
- `tests/test_textifai_open_design_setup.py`
- `tests/fixtures/textifai/viewer_wiring/**`
- `tests/fixtures/textifai/design_tooling/expected/*after_sp092.json`

## SP092 Context
SP-092 creó materializer VaERL -> Markdown, backlink graph index, vault sintético, docs de diseño y Open Design audit/clone. No conectó UI viewer ni dejó Open Design runtime operativo.

## Viewer Wiring Inventory
Viewer tenía endpoints `projects`, `graph`, `note`, `artifacts`; Notes ya existía pero como file browser básico. SP-093 añade contrato Markdown-first: `markdown_manifest`, `markdown_graph_index`, note metadata enriquecida y graph derivado de Markdown index.

## Markdown Manifest Project Reader Patch
`project_reader` ahora detecta proyectos Markdown con `99_System/markdown_manifest.json`, `99_System/markdown_graph_index.json` y variantes `System/*`. Si hay graph index Markdown, `build_graph()` lo usa como graph principal. Fallback limitado: ingestion graph solo cuando no existe graph index Markdown.

## Wiki / Markdown Browser MVP
Tab `Wiki` sustituye semánticamente a `Notes`. Añade search por title/path/tag/alias, filtros kind/tag/status, note detail con frontmatter, tags, backlinks, outgoing links, degree y local graph summary. Read-only; no write-back.

## Node Detail from Markdown + VaERL Data
Graph node detail usa nota Markdown si existe: tags, degree, backlinks/outgoing count, frontmatter, Markdown render, local graph. VaERL/obsidian fallback queda como apoyo si no hay note.

## Graph Readability V1
Graph añade degree-based node sizing, force collision más fuerte por radius, status filter, local graph mode, selected-node highlight, edge labels y legend. Limitación: layout sigue heurístico y puede solapar en grafos densos.

## Dashboard / Overview Patch
Overview muestra wiki notes, backlink edges, tags, orphan notes, unresolved links, relationship count y CTA `Open Wiki` / `Open Graph`. Artifacts/Debug queda secundario.

## Synthetic Viewer Project
Proyecto sintético commiteable creado en `tests/fixtures/textifai/viewer_wiring/input/sample_markdown_viewer_project_after_sp092/`. Contiene Markdown notes sintéticas + `99_System/markdown_manifest.json` + `99_System/markdown_graph_index.json`.

## Viewer Manual Review Server
Viewer sintético levantado en `http://127.0.0.1:8871` con root `tests/fixtures/textifai/viewer_wiring/input`. Endpoints `/`, `/api/projects`, `/api/projects/<id>`, `/api/projects/<id>/graph` respondieron OK.

## Open Design Install / Skill Setup
Open Design externo en `/tmp/textifai_dev_tools/open-design`. `corepack pnpm install --frozen-lockfile` ejecutado. Daemon CLI compilado con `corepack pnpm --filter @open-design/daemon build`. Skills detectadas: 132. Design systems detectados: 150. Recomendados para TextifAI: `design-review`, `plan-design-review`, `web-design-guidelines`, `d3-visualization`, `design-consultation`; design system base: `dashboard`.

## Open Design Codex/MCP Setup
`od mcp` disponible tras build de daemon CLI. Setup documentado en `docs/textifai-open-design-codex-setup.md` con snippet MCP manual. No se editó config global Codex. Runtime web/daemon bloqueado por Node `~24`; entorno actual tiene Node `v22.22.2`.

## Open Design First TextifAI Design Review
No se ejecutó live Open Design por bloqueo Node 24. Se generó review privado/manual usando catálogo y checklist en `/tmp/textifai_private_provider_runs/sp093_markdown_wiki_viewer_open_design/20260526T155501Z/open_design_outputs/textifai_design_review_sp093.md`.

## Design Docs Update
`docs/textifai-design-direction.md` y `docs/textifai-ui-review-checklist.md` actualizados con acceptance SP-093 para graph/wiki/node detail y cadencia Open Design.

## Product Decision
`markdown_wiki_viewer_ready_open_design_partial`

## Recommended Next Phase
Phase 1.3.M-b5c-4w — Editable Wiki + VaERL Patch Proposal Queue + Graph Layout Refinement + live Open Design review on Node 24.

## What Worked
- Backend viewer carga manifest/index Markdown.
- Wiki browser MVP visible y author-facing.
- Node detail incluye backlinks/tags/local graph.
- Graph index Markdown alimenta graph.
- Open Design dependencias instaladas fuera del repo y CLI MCP documentado.

## What Failed
- Open Design web/daemon no pudo arrancar con Node 22; requiere Node 24.
- No editor Markdown/write-back aún.
- Graph readability mejoró pero no resuelve grafos densos grandes.

## Data Written
- Código viewer.
- Proyecto sintético viewer.
- Reports commit-safe.
- Docs setup/diseño.
- Private design review en `/tmp`.

## Privacy / Non-committed Output
No provider calls. No OpenAI. No DeepSeek. No private prose. No `/tmp` commit. No Open Design repo commit. No generated private output commit.

## Tests Added / Updated
- `tests/test_textifai_viewer_markdown_wiring.py`
- `tests/test_textifai_open_design_setup.py`
- Regresión SP-092 mantenida.

## Validation Performed
- `py_compile` de `project_reader.py`.
- `node --check` de `app.js`.
- Endpoint check viewer sintético en puerto 8871.
- Suites unitarias requeridas pendientes en log final de ejecución.

## Safety Constraints
No provider calls. No OpenAI. No DeepSeek. No retry. No full-source. No write-back. No runtime dependency Open Design. No package changes TextifAI.

## Known Limitations
- Open Design live review requiere Node 24.
- Wiki es read-only.
- Graph local mode es neighborhood depth 1.
- Markdown edits aún no generan patch proposals.

## Future Extensions
- Editor Markdown read/write con proposal queue.
- VaERL patch proposal review flow.
- Graph layout Web Worker o deterministic layout cache.
- Full Open Design live design sprint.
- Better markdown renderer/sanitizer if needed.

## Runtime Changes
Viewer now exposes Markdown manifest/index payloads and can render Markdown-index-backed graph/note data. Open Design installed only under `/tmp` external dev path.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
