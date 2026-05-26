# First-party VaERL Platform Architecture: Quartz/Obsidian Adaptation Spike

## Product Reading
README define TextifAI como Semantic Story Engine para autores, con VaERL como semantic source of truth. TextifAI no es editor AI superficial, ni importer de Obsidian, ni wrapper de prompt largo. Debe convertirse en semantic workbench first-party con Markdown editable, proyecciones sobre VaERL y correcciones de autor que vuelven a VaERL.

## Scope
- Leer README como doctrina.
- Auditar repo actual vs doctrina.
- Auditar Quartz y ruta Obsidian-like.
- Definir arquitectura first-party VaERL/Markdown/Graph/Wiki/AI.
- Definir materialization contract y cleanup plan.
- Crear spike provider-free sintético pequeño.

## Files Changed
- `tests/fixtures/textifai/platform_architecture/input/sample_vaerl_for_markdown_materialization.json`
- `tests/fixtures/textifai/platform_architecture/expected/*.json`
- `tests/test_textifai_platform_architecture.py`
- `docs/handoffs/safepoint-091_first-party-vaerl-platform-quartz-obsidian-spike.md`

## README Product Doctrine
VaERL es semantic source of truth. ECC entiende intención/contexto. Views son proyecciones: Codex View, Story Bible View, Review Queue, Editor View, Query Layer, future author chat. Markdown es first-class output. Correcciones del autor deben volver a VaERL. Replayability importa. Grounding gana a giant prompts.

## Current Repo vs README Gap
Alineado: ingestión, resolución, review queue, obsidian-style artifacts, viewer MVP, VaERL index/contracts. Gap: falta plataforma first-party integrada; viewer sigue parcial/debug; markdown materialization no es substrate editable VaERL-first; surfaces de editor/query/chat faltan.

## Quartz Architecture Audit
Quartz sirve como referencia/patrón, no como plataforma final. Aporta ideas útiles: wikilinks, backlinks, graph, tags, previews, plugin-style pipeline. No resuelve edición interactiva, write-back a VaERL ni canon governance. Requiere review de licencia antes de copiar código.

## Existing Obsidian-like Path Reuse
Reutilizable: frontmatter, note_path, tags, wikilink/backlink parser, review_queue semantics, VaERL index. A reemplazar: obsidian_import como truth source y dependencia de herramienta externa. Ruta objetivo: VaERL core -> Markdown materialization -> graph/backlink index -> viewer/wiki/editor.

## First-party VaERL Platform Architecture
Capas:
1. Ingestion/ECC
2. VaERL core
3. Markdown materialization
4. Graph/index/backlink
5. Viewer/KB manager
6. Wiki view
7. AI authoring suite
8. Review/retry/canon governance

## VaERL → Markdown Materialization Contract
Carpetas conceptuales:
- `Characters/`
- `Places/`
- `Events/`
- `Objects/`
- `Concepts/`
- `Chapters/`
- `Reviews/`
- `System/`
Frontmatter con `vaerl_id`, `kind`, `canonical_label`, `aliases`, `tags`, `status`, `review_state`, `chapter_ids`, `source_refs`. Wikilinks/backlinks derivados. Edits generan patch proposals hacia VaERL, no write-back silencioso.

## Dashboard / Graph / Wiki / Editor Surfaces
MVP first-party debe incluir:
- Dashboard
- Graph global/local
- Wiki Markdown browser + backlinks + search
- Node detail útil
- AI authoring suite por línea/párrafo + Character Lab + grounded query

## Quartz / Obsidian Adaptation Strategy
Copiar/adaptar patrones, no workflow externo. Evitar Quartz como dependencia core o generated site final. Posible fork selectivo tras license review. Obsidian/Quartz inspiran estructura de notas, graph UX y navegación wiki.

## Lean Legacy Cleanup Plan
Mantener: VaERL core, review semantics, parser utilities, viewer server base. Adaptar: obsidian_import hacia projection subordinada. Retirar/deprecar: artifacts como author UX principal, fallback ambiguo, source of truth duplicado.

## Optional Provider-free Spike
Incluido fixture sintético VaERL -> Markdown materialization index -> graph index para demostrar contrato mínimo provider-free.

## Commit-safe vs Private Decision Handoff
Commit-safe: este handoff + reports JSON. Private packet:
- root: `/tmp/textifai_private_provider_runs/sp091_first_party_vaerl_platform/<timestamp>`
- `decision_handoff_private.md`
Subir primero a ChatGPT si hace falta:
1. `decision_handoff_private.md`

## Product Decision
`first_party_vaerl_platform_architecture_ready_for_implementation`

## Recommended Next Phase
Phase 1.3.M-b5c-4u — VaERL Markdown Materialization + Backlink Index MVP

## What Worked
- README permitió fijar doctrina clara.
- Repo ya tiene piezas VaERL/Obsidian-like reutilizables.
- Quartz aporta patrones útiles.
- Arquitectura incremental queda definida sin providers.

## What Failed
- No se auditó código Quartz local porque no está en repo; audit se apoya en docs públicas/GitHub.
- No se implementó plataforma ni materializer real; solo contrato/spike.

## Data Written
- Reports commit-safe de arquitectura.
- Fixture sintética provider-free.
- Private decision handoff ligero en `/tmp`.

## Privacy / Non-committed Output
No commit de `/tmp`, prompts privados, raw outputs privados ni prose largo.

## Tests Added / Updated
- `tests/test_textifai_platform_architecture.py`

## Validation Performed
- unittest SP-091
- suites previas de viewer/patch/audit
- status/diff git

## Safety Constraints
No provider calls. No OpenAI. No DeepSeek calls. No retry. No full-source. No write-back.

## Known Limitations
- Quartz audit no baja a component-level code review completo.
- No editor first-party implementado aún.
- No materializer runtime implementado aún.

## Future Extensions
- Materializer MVP
- backlink/graph index incremental
- wiki surfaces
- author editing feedback loop
- AI authoring grounded on VaERL

## Runtime Changes
Ninguno. Fase arquitectura/spike/reportes.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
