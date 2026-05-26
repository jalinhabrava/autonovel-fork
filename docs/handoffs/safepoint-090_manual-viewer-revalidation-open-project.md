# Manual Viewer Revalidation with Patched VaERL Projection + Open Project Flow

## Product Reading
TextifAI es motor de ingestión VaERL, viewer/manager author-facing y base para editor interactivo. Viewer no puede depender de que Codex deje un proyecto correcto cargado por accidente; debe permitir abrir/cambiar proyecto y mostrar grafo útil con labels reales.

## Scope
- Revalidación manual provider-free contra `viewer_project_sp089`.
- Patch mínimo de project discovery.
- Patch mínimo de Open Project / Abrir proyecto.
- Validación endpoint/data-level de overview/graph/detail.
- Handoff commit-safe + handoff privado.

## Files Changed
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/app.js`
- `textifai/web_viewer/static/styles.css`
- `tests/test_textifai_manual_viewer_revalidation.py`
- `tests/fixtures/textifai/viewer_revalidation/expected/*.json`
- `docs/handoffs/safepoint-090_manual-viewer-revalidation-open-project.md`

## SP089 Context
SP-089 corrigió proyección VaERL y retry/review mapping, pero no reinició viewer server. Usuario seguía viendo `viewer_project` viejo con labels sintéticas. SP-090 revalida server+discovery+UI mínima sobre `viewer_project_sp089`.

## Commit-safe vs Private Decision Handoff
- Commit-safe repo handoff: este archivo + reports agregados/métricas.
- Private decision handoff: ejemplos reales en `/tmp/textifai_private_provider_runs/sp090_manual_viewer_revalidation/<timestamp>/`.
- Repo no contiene source prose largo, raw outputs ni dump completo del graph real.

## Private Graph Presence
`viewer_project_sp089/99_System/ingestion_graph.json` existe, parsea y contiene graph reproyectado con labels reales. Reporte commit-safe: `tests/fixtures/textifai/viewer_revalidation/expected/sp089_private_graph_presence_after_sp089.json`.

## Open Project Discovery
Causa raíz confirmada: discovery solo detectaba proyectos con `obsidian_import.json` o `review_queue.json`; ignoraba proyectos con solo `ingestion_graph.json`. Patch hecho para descubrir ambos proyectos bajo root servido.

## Open Project UI Patch
Se añadió panel visible `Open Project / Abrir proyecto` en sidebar:
- lista proyectos descubiertos bajo root;
- muestra proyecto activo;
- muestra recomendado;
- muestra counts resumidos y synthetic label count;
- botón `Open` read-only;
- sin browsing arbitrario del filesystem.

## Manual Viewer Server
Server revalidado con root:
`/tmp/textifai_private_provider_runs/sp087_twenty_chapter_e2e_viewer/20260526T100011Z/20260526T100049Z`

## Server URL / Stop Command
- URL: `http://127.0.0.1:8870`
- Host: `0.0.0.0`
- Project recomendado: `viewer_project_sp089`
- Stop: `kill 1135997`

## Endpoint Validation
- `/` -> 200
- `/api/projects` -> 200, lista `viewer_project` y `viewer_project_sp089`
- `/api/projects/<sp089_id>` -> 200
- `/api/projects/<sp089_id>/graph` -> 200
- Graph correcto: 430 nodes, 91 edges, synthetic labels 0.

## Viewer Data Quality
Overview, Graph y Detail reciben datos útiles. Reporte commit-safe: `tests/fixtures/textifai/viewer_revalidation/expected/sp089_viewer_data_quality_after_sp089.json`.

## Overview Data
Overview expone capítulos procesados, ready/review/retry/failed, relationship count, node counts by kind, warnings y CTA `Review results`.

## Graph Data
Graph API devuelve labels reales y relaciones semánticas reales. `viewer_project` viejo sigue visible y conserva synthetic labels; `viewer_project_sp089` queda marcado como recomendado.

## Node Detail Data
Node detail payload contiene label real, kind, facts, source refs y relationships in/out cuando existen. Persisten nodos débiles con faltas parciales de refs/aliases/facts.

## Private Decision Packet
Root privado:
- `/tmp/textifai_private_provider_runs/sp090_manual_viewer_revalidation/20260526T134829Z`
Archivos:
- `decision_handoff_private.md`
- `sp089_private_graph_examples_private.md`
- `viewer_data_quality_examples_private.md`
Upload first for ChatGPT review:
1. `decision_handoff_private.md`
2. `sp089_private_graph_examples_private.md`
3. `viewer_data_quality_examples_private.md`

## Product Decision
`viewer_manual_revalidation_passed_with_minor_warnings`

## Recommended Next Phase
Phase 1.3.M-b5c-4t — Author-facing Viewer Quality Patch or Manual 20-chapter Story Map Review

## What Worked
- Discovery ahora encuentra proyecto viejo y parcheado.
- `viewer_project_sp089` queda recomendado.
- Endpoints sirven graph con labels reales.
- Overview usa writer outcome correcto.
- Open Project deja de depender de estado accidental del browser.

## What Failed
- Browser abierto previamente necesita refresh manual para cargar JS/UI parcheada.
- Siguen warnings de missing source refs en subset de nodos.
- Detail panel aún puede necesitar más pulido author-facing.

## Data Written
- Código viewer patch.
- Reports commit-safe en `tests/fixtures/textifai/viewer_revalidation/expected/`.
- Packet privado SP-090 en `/tmp/.../sp090_manual_viewer_revalidation/20260526T134829Z`.

## Privacy / Non-committed Output
No commit de `/tmp`, private decision handoff, raw graph dump, source prose largo, prompts ni raw provider outputs.

## Tests Added / Updated
- `tests/test_textifai_manual_viewer_revalidation.py`

## Validation Performed
- unittest SP-090 y suites relacionadas.
- endpoint checks contra server en `0.0.0.0:8870`.
- verificación manual pendiente por usuario en browser refrescado.

## Safety Constraints
No provider calls. No OpenAI. No DeepSeek calls. No retry. No full-source. No write-back. No browser automation. No screenshots. No arbitrary filesystem browsing.

## Known Limitations
- Necesita refresh del browser ya abierto.
- Algunos nodos siguen sin refs completas.
- Visual polish author-facing aún MVP.

## Future Extensions
- Pulido de detail summarization.
- Warning triage author-facing.
- Materialización richer de notes/tags/backlinks.

## Runtime Changes
Discovery incluye proyectos con `ingestion_graph.json`. UI muestra Open Project explícito. No cambios write-back.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
