# Controlled 20-chapter E2E: Ingestion to Viewer Manual Review Server

## Product Reading
SP-083 validó natural multi-chunk real en 4 capítulos. SP-084 cerró contrato fail-only retry + writer outcome. SP-085 ejecutó retry real de capítulos afectados con backlog limpio y 3 ready + 1 needs review. SP-086 confirmó compatibilidad viewer MVP y adapter provider-agnostic. Este safepoint ejecuta primer flujo real ch_001–ch_020: ingestión, outcome escritor, rerun plan interno, proyección de grafo, y servidor viewer manual-review.

## Scope
- DeepSeek-only, Flash-first, ch_001–ch_020.
- No OpenAI, no auto-switch invisible, no full novel, no write-back definitivo.
- Provider calls reales permitidas bajo cap 96.
- Generación de private decision packet en `/tmp`.
- Viewer MVP read-only con `--host 0.0.0.0` para revisión manual.

## Files Changed
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_e2e_execution_plan_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_e2e_summary_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_chapter_results_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_internal_fail_rerun_plan_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_writer_outcome_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_graph_projection_summary_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_viewer_manual_review_server_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_viewer_writer_expectation_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_general_pipeline_learnings_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_deepseek_specific_learnings_after_sp086.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/twenty_chapter_e2e_decision_after_sp086.json`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `docs/handoffs/safepoint-087_twenty-chapter-e2e-viewer-manual-review.md`

## SP086 Context
- Viewer MVP inventariado y operativo.
- `adapt_ingestion_graph_to_viewer_graph()` disponible.
- Carga de `99_System/ingestion_graph.json` habilitada.
- Backend/API smoke previo en verde.

## Source / Chapter Scope
- Fuente: `/home/david/OnT/王者の杖.md`
- Scope: `ch_001` a `ch_020` inclusive.
- Sin commit de source prose.

## Execution Plan
- Plan provider-free generado antes de llamadas.
- Flash-first: `deepseek-v4-flash` con profile `deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1`.
- Calls plan base: 40; reserva continuation: 20; total plan con reserva: 60; cap: 96; fits cap: true.
- Stop conditions incluidas en reporte (cap, wrong-chapter continuation repetido, baja cobertura refs, invalid reductions, auth/provider errors, write-back inesperado).

## Provider Calls
- Ejecutadas: **41** (40 plan base + 1 continuation real).
- Cap: 96.
- Modelo usado: `deepseek-v4-flash`.
- Pro targeted: no usado en este pase.

## Long-run Handling
- Progress log incremental en private packet: `progress_log.jsonl`.
- Registro por run con índice, chapter, model, chunk/profile y timestamps.
- No cancelación manual ni timeout fatal observado.

## Runtime Results
- Reductions válidas: 20/20.
- Continuations activadas: 1.
- Provider call budget: dentro de cap.
- Assessment técnico del run indica calidad heterogénea; múltiples capítulos quedan para second pass.

## Chapter Results
- Totales writer-facing tras mapeo: `ready=6`, `needs_retry=13`, `needs_review=1`, `failed=0`.
- Reporte por capítulo en `twenty_chapter_chapter_results_after_sp086.json`.

## Writer-facing Outcome
- Reporte: `twenty_chapter_writer_outcome_after_sp086.json`.
- Estado: `success_with_retry_available`.
- Total capítulos: 20.
- CTA principal: `Retry pending chapters` (scope `affected_chapters_only`).
- CTA secundaria: `Later`.
- Sin términos internos en mensaje writer-facing.

## Internal Fail-only Rerun Plan
- Reporte: `twenty_chapter_internal_fail_rerun_plan_after_sp086.json`.
- Retryable chapters: 13.
- Excluye capítulos exitosos.
- Safe rerun: `affected_chapters_only`, sin full ingestion.
- Incluye unidades reintentables, strategy sugerida y calls estimadas.

## Graph Projection
- Se generó grafo provisional en privado:
  - `/tmp/textifai_private_provider_runs/sp087_twenty_chapter_e2e_viewer/20260526T100011Z/20260526T100049Z/viewer_project/99_System/ingestion_graph.json`
- Reporte público: `twenty_chapter_graph_projection_summary_after_sp086.json`.
- Conteos: 100 nodos, 40 edges, 20 capítulos, coverage refs resumen 1.0 (metadata-level synthetic projection).
- Adapter usado: `textifai.import_review.viewer_graph_adapter.adapt_ingestion_graph_to_viewer_graph`.

## Viewer Manual Review Server
- Servidor levantado en background con host obligatorio `0.0.0.0`.
- Endpoints validados 200:
  - `/`
  - `/api/projects`
  - `/api/projects/<id>`
  - `/api/projects/<id>/graph`
- Sin screenshots automáticos ni browser automation.

## Server URL / Stop Command
- URL local: `http://127.0.0.1:8870`
- Host bind: `0.0.0.0`
- Port: `8870`
- Project ID: `tmp__textifai_private_provider_runs__sp087_twenty_chapter_e2e_viewer__20260526T100011Z__20260526T100049Z__viewer_project`
- Command used:
  - `/home/david/.local/bin/uv run python -m textifai.web_viewer.server --root /tmp/textifai_private_provider_runs/sp087_twenty_chapter_e2e_viewer/20260526T100011Z/20260526T100049Z --host 0.0.0.0 --port 8870`
- PID: `542735`
- Log: `/tmp/textifai_private_provider_runs/sp087_twenty_chapter_e2e_viewer/20260526T100011Z/20260526T100049Z/viewer_server.log`
- Stop command: `kill 542735`

## Viewer Writer Expectation
- Reporte: `twenty_chapter_viewer_writer_expectation_after_sp086.json`.
- Writer ve mapa narrativo, capítulos procesados, ítems con revisión, y CTA.
- Mensajería mantiene lenguaje no técnico.

## General Pipeline Learnings
- Flujo ingestion→outcome→rerun-plan→graph-projection→viewer-server funciona extremo a extremo bajo cap.
- Viewer MVP puede revisar proyecto sandbox sin write-back.
- Fail-only retry contract sigue aplicable a lotes grandes.

## DeepSeek-specific Learnings
- Flash-first completó run bajo cap.
- 1 continuation real observada.
- No Pro targeted en este pase; conviene aplicar Pro solo en subset afectado en siguiente fase.

## Private Decision Packet
- Root: `/tmp/textifai_private_provider_runs/sp087_twenty_chapter_e2e_viewer/20260526T100011Z/20260526T100049Z`
- Incluye per-call manifests/prompts/payloads redacted/responses/usage/finish_reason/validation/failure-mode/response-control.
- Incluye fase: execution/chapter/summary/source-ref/truncation/patch/thin/rerun/outcome/graph/viewer/decision private notes.
- No commit de `/tmp`.

## Product Decision
`twenty_chapter_e2e_partial_needs_retry_or_viewer_patch`

## What Worked
- Plan <= cap y ejecución real estable (41 calls).
- 20/20 reductions válidas.
- Outcome writer-facing y rerun plan interno generados.
- Grafo provisional viewer-ready en sandbox.
- Viewer server manual-review activo y endpoints 200.

## What Failed
- Calidad insuficiente en subset grande: 13 capítulos quedan en retry y 1 en review.
- Requiere fase de retry targeted antes de escalar a full-source mayor.

## Data Written
- Reports privacy-safe en `tests/fixtures/textifai/real_provider_dryrun/expected/`.
- Handoff en `docs/handoffs/`.
- Artefactos privados y viewer sandbox en `/tmp`.

## Privacy / Non-committed Output
- No commit de `/tmp`, prompts privados, outputs privados, source prose, logs runtime privados.
- No write-back definitivo.

## Tests Added / Updated
- `tests/test_textifai_real_provider_dryrun_guards.py` actualizado con guardas SP-087.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_viewer_preflight`
- `uv run python -m unittest -v tests.test_textifai_chunking_reduction_preflight`
- `uv run python -m unittest -v tests.test_textifai_prompt_experiment_observability`
- `uv run python -m unittest -v tests.test_textifai_deepseek_family_profiles`
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- Viewer endpoint check manual (200 for root/projects/project/graph).

## Safety Constraints
- DeepSeek only.
- No OpenAI.
- No auto-switch invisible.
- No full novel.
- No write-back definitivo.
- No screenshots automáticos.
- No browser automation.

## Known Limitations
- 13 capítulos aún requieren second pass.
- Viewer revisión visual queda manual por usuario.

## Future Extensions
- Retry targeted de capítulos afectados con strategy explicit (Flash+targeted Pro).
- Consolidated outcome post-rerun.
- Gate de readiness para Phase A más grande.

## Runtime Changes
- Ningún cambio de runtime core requerido para levantar viewer; se usó infraestructura MVP existente.

## Write-back
No.

## Branch
`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
Phase 1.3.M-b5c-4q — Targeted Retry Set + Manual Viewer Review Consolidation before larger full-source Phase A.
