# Viewer Compatibility Preflight for Ingestion Graph Results

## Product Reading
SP-083 proved broader natural multi-chunk DeepSeek dry-run. SP-084 closed provider-free retry and writer outcome contracts. SP-085 executed affected-only retry for ch_106 and ch_115 with 19 provider calls, 4/4 final reductions valid, source_ref coverage 1.0, retry backlog cleared, and final writer outcome of 3 ready plus 1 needs review. Before spending calls on first-20-chapter e2e, this safepoint checks whether current MVP viewer can represent ingestion graph results without provider calls, full-source, or write-back.

## Scope
Provider-free viewer compatibility preflight only. Audit current viewer contract, inventory ingestion graph output shape, add minimal provider-agnostic adapter, create privacy-safe graph fixture, smoke-test current viewer loading path, and document readiness for the 20-chapter e2e.

## Files Changed
- `textifai/import_review/viewer_graph_adapter.py`
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/app.js`
- `tests/test_textifai_viewer_preflight.py`
- `tests/fixtures/textifai/viewer_preflight/input/sample_ingestion_graph_after_sp085.json`
- `tests/fixtures/textifai/viewer_preflight/expected/*.json`
- `docs/handoffs/safepoint-086_viewer-compatibility-preflight.md`

## SP085 Context
SP-085 left a consolidated writer-facing outcome with 4 chapters processed, 3 ready, 1 needing review, no retry backlog, no write-back, and full-source Phase A allowed with review warnings.

## Existing Viewer Inventory
Current MVP viewer exists in `textifai/web_viewer/server.py`, `textifai/web_viewer/project_reader.py`, and `textifai/web_viewer/static/app.js`. It exposes `/api/projects`, `/api/projects/<id>`, `/api/projects/<id>/graph`, `/api/projects/<id>/canon`, `/api/projects/<id>/artifacts`, note reads, and artifact reads. Project discovery expects `99_System/obsidian_import.json` or `99_System/review_queue.json`.

## Ingestion Graph Output Inventory
Current ingestion outputs are mostly canon/review artifacts plus dry-run reports. Raw ingestion graph-like data is not always directly viewer-loadable. It can contain people, places, ideas, items, events, links, chapter IDs, and source refs, but lacks viewer-specific role/tags/type fields.

## Viewer Expected Graph Contract
Viewer graph expects `nodes` and `edges`. Nodes need `id`, `label`, `kind`; `role`, `tags`, `note_path`, `entity`, and `chapter` are optional but useful. Edges need `source`, `target`, and `type`; `label`, `kind`, `chapter_ids`, and `source_refs` are optional. `edge.type` drives SVG tooltip.

## Graph Adapter
Added `adapt_ingestion_graph_to_viewer_graph()` in `textifai/import_review/viewer_graph_adapter.py`. Adapter is provider-agnostic, keeps `source_refs`, normalizes nodes/edges, adds `type` from `label`, adds role/tags/status, and records warnings for missing refs or endpoints. No DeepSeek logic.

## Sample Viewer Graph Fixture
Created synthetic privacy-safe fixture with characters, places, concepts, objects, events, relations, unresolved mention, synthetic source refs, ready chapters, and one needs-review chapter. No source prose, prompts, outputs, provider payloads, or private packet data.

## Viewer Smoke Test
Backend/API smoke passed with current viewer server handler: `/`, `/api/projects`, `/api/projects/<id>`, and `/api/projects/<id>/graph` returned 200. Graph loaded 7 nodes and 4 edges from `ingestion_graph.json` through current project reader path. No browser screenshot captured.

## Screenshots / Logs
No screenshots committed. Smoke result held in command output only. No `/tmp` artifacts committed.

## Writer-facing Viewer Expectation
Writer should see a story map of people, places, events, items, ideas, chapter status, review markers, and basic story links. Writer should not see engine internals, raw service details, developer logs, or provider diagnostics.

## General Pipeline Learnings
Core needs a normalized graph projection between ingestion output and viewer. Source refs can survive this projection. Chapter/review status maps cleanly to role/tags. The 20-chapter e2e should generate viewer-ready graph artifacts before UI smoke.

## Provider-specific Learnings
None required. Viewer compatibility must not depend on DeepSeek, OpenAI, model profiles, or provider telemetry.

## Product Decision
`viewer_preflight_ready_with_minor_warnings`. MVP viewer can load representative graph results through minimal adapter. Warnings remain: browser screenshot not captured, edge evidence display is inspectable in data but still MVP-level visually, raw ingestion outputs need adapter.

## What Worked
- Existing viewer has usable graph endpoint and SVG renderer.
- Minimal `ingestion_graph.json` path can feed viewer graph.
- Adapter preserved source refs and made edges viewer-compatible.
- Provider-free tests and HTTP smoke passed.

## What Failed
No fatal blocker. Full browser rendering screenshot was not captured. Visual evidence display remains basic.

## Data Written
Privacy-safe fixtures and reports under `tests/fixtures/textifai/viewer_preflight/`. Handoff under `docs/handoffs/`. No real source prose or provider output written.

## Privacy / Non-committed Output
No `/tmp` committed. No prompts, outputs, API keys, provider responses, or full novel source committed. Fixture labels are synthetic.

## Tests Added / Updated
Added `tests/test_textifai_viewer_preflight.py`. Updated viewer reader to load `ingestion_graph.json` via adapter. Updated viewer node detail to show source refs when present.

## Validation Performed
- `/home/david/.local/bin/uv run python -m unittest -v tests.test_textifai_viewer_preflight`
- `/home/david/.local/bin/uv run python -m unittest -v tests.test_textifai_chunking_reduction_preflight`
- `/home/david/.local/bin/uv run python -m unittest -v tests.test_textifai_prompt_experiment_observability`
- `/home/david/.local/bin/uv run python -m unittest -v tests.test_textifai_deepseek_family_profiles`
- `/home/david/.local/bin/uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `/home/david/.local/bin/uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `/home/david/.local/bin/uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' /home/david/.local/bin/uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- HTTP smoke over current viewer server handler.

## Safety Constraints
No provider calls. No OpenAI. No DeepSeek. No full-source execution. No write-back. No `/tmp` commit. No private prompts/outputs.

## Known Limitations
No browser screenshot. Viewer source-ref display is basic. Adapter assumes normalized graph fields or category lists; raw reductions still need upstream projection.

## Future Extensions
Add browser smoke screenshot, first-class evidence panel, explicit writer-facing chapter status panel, and 20-chapter e2e viewer artifact generation.

## Runtime Changes
Minimal provider-free runtime: viewer can load `99_System/ingestion_graph.json` if present and adapt it to viewer graph.

## Write-back
No write-back.

## Branch
`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
Phase 1.3.M-b5c-4p — Controlled 20-chapter E2E: Ingestion to Viewer Smoke Test
