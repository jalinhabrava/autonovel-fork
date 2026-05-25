# Real DeepSeek E2E Dry-run with Private Decision Packet

## Product Reading
- SP-075 validó dirección chunk->partial->reduction con mejora fuerte vs non-chunked pero dejó truncation + source_refs item-level.
- SP-076 endureció contrato provider-free: source-ref carry-forward, budget dinámico, response_control, truncation/continuation.
- SP-077 valida en vivo robustez e2e real con esos ajustes y packet privado obligatorio.

## Scope
- Ejecutado full real DeepSeek e2e en capítulos controlados con cap 24 calls.
- Sin OpenAI, sin auto-switch, sin write-back.
- Commit solo reportes privacy-safe + tests/docs + script dev.

## Files Changed
- scripts/dev/real_deepseek_e2e_dryrun.py
- tests/test_textifai_real_provider_dryrun_guards.py
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_execution_plan_after_sp076.json
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_summary_after_sp076.json
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_chunk_results_after_sp076.json
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_reduction_summary_after_sp076.json
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_budget_report_after_sp076.json
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_source_ref_audit_after_sp076.json
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_truncation_continuation_audit_after_sp076.json
- tests/fixtures/textifai/real_provider_dryrun/expected/full_deepseek_e2e_decision_after_sp076.json
- docs/handoffs/safepoint-077_full-deepseek-e2e-validation-source-refs-continuation.md

## Environment Check
- DEEPSEEK_API_KEY present: true (hash fingerprint capturado en terminal, sin secreto completo).

## Execution Plan
- assessment plan: real_deepseek_e2e_execution_plan_ready
- chapters seleccionados: ['ch_001', 'ch_002', 'ch_003']
- models: ['deepseek-v4-flash', 'deepseek-v4-pro']
- planned calls: 12
- planned with continuation reserve: 18
- cap: 24

## Source / Chapters
- source file: hash-only reportado, sin texto completo.
- obligatorios: ch_002, ch_003.
- extra seleccionado por longitud: ch_001.

## Models and Profiles
- deepseek-v4-flash -> deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1
- deepseek-v4-pro -> deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1

## Structured Chunk Plan
- chunk plan generado con char ranges + estimated tokens por chunk.
- en esta corrida cada capítulo quedó 1 structured chunk + 1 reduction por modelo.

## Provider Calls
- provider real calls ejecutadas: 13 (cap 24).
- se activó 1 continuation/reparación.

## Long-run Handling
- progress log incremental en packet privado (`progress_log.jsonl`).
- cada call registra started_at / finished_at / duration / output_file_size.
- no cancelación prematura.

## Output Budget Resolution
- budget dinámico aplicado por run (`effective_max_output_tokens`) desde resolver SP-076.
- default DeepSeek observado: 8192 (vía profile/model resolver, no literal disperso).
- report en `full_deepseek_e2e_budget_report_after_sp076.json`.

## Runtime Results
- assessment final: real_deepseek_e2e_validation_passed_with_review_warnings.
- best reduction run: ch_002__deepseek_v4_flash score=59.0.
- comparación SP075: best score 57.5 -> 59.0.

## Chunk-level Results
- chunk outputs parseables mayormente válidos.
- thin output warnings detectados en 6 chunk calls.

## Reduction/Aggregation Results
- reductions válidas: 5/6.
- fallo principal: ch_001__deepseek_v4_pro con finish_reason length y JSON no parseable tras continuation.

## Source-ref Audit
- coverage global item-level source_refs: 0.8333333333333334.
- parseable reduction runs: 5.
- missing source_ref runs en parseable outputs: 0.

## Truncation / Continuation Audit
- continuation triggered: 1.
- continuation problem count: 1.
- caso crítico: Pro reduction ch_001 truncado (`finish_reason_length`) y continuation no reparó parseabilidad.

## Usage / Finish Reason
- usage capturada en packet por call (`provider_usage.json`).
- resumen: {'runs_with_usage': 12, 'max_total_tokens': 14665, 'max_completion_tokens': 8192}.
- finish_reason capturado por call (`finish_reason_report.json`).

## Thin Output Warnings
- warnings incluidos en chunk/reduction rows para revisión humana.

## Failure Modes
- observado principal: `finish_reason_length` en 1 reduction Pro.
- resto runs con `stop` y parseable JSON.

## Comparison vs SP075
- score tope mejora 57.5 -> 59.0.
- source_ref item-level mejorado en outputs parseables.
- truncation sigue existiendo en una rama Pro; ya detectable y auditada.

## Private Decision Packet
- root exacto: /tmp/textifai_private_provider_runs/sp077_full_deepseek_e2e_validation/20260525T114840Z
- archivos clave:
  - README.md
  - execution_plan_private.md
  - chunk_plan_private.md
  - matrix_summary_private.md
  - matrix_comparison_private.md
  - source_ref_audit_private.md
  - truncation_recovery_audit_private.md
  - reduction_trace_private.md
  - decision_notes_private.md
  - per-call: run_manifest.json, final_prompt_sent.md, provider_request_payload.redacted.json, provider_response_raw.txt, provider_response_parsed.json, provider_usage.json, finish_reason_report.json, response_control_report.json
- recomendado subir primero a ChatGPT:
  1) matrix_summary_private.md
  2) matrix_comparison_private.md
  3) source_ref_audit_private.md
  4) truncation_recovery_audit_private.md
  5) reduction_trace_private.md

## Handoff Visibility Summary
- Incluye por run: model/profile/chapter/chunk, chunk spans, budget efectivo, usage/finish_reason, failure mode, continuation status.
- Datos suficientes para decisión sin abrir prompts completos.

## Product Decision
- real_deepseek_e2e_validation_passed_with_review_warnings

## What Worked
- Pipeline e2e real estable bajo cap.
- Budget dinámico aplicado y reportado.
- source_ref carry-forward funcional en reductions parseables.
- packet privado completo generado en `/tmp`.

## What Failed
- 1 reduction Pro truncada por límite (`finish_reason_length`).
- continuation intentado pero no logró JSON parseable en ese caso.

## Data Written
- Reports privacy-safe en fixtures `full_deepseek_e2e_*_after_sp076.json`.
- Packet privado completo en `/tmp` (no versionado).

## Privacy / Non-committed Output
- No commit de `/tmp`.
- No prompts/outputs completos en repo.
- No API keys en fixtures.

## Tests Added / Updated
- tests/test_textifai_real_provider_dryrun_guards.py:
  - parse + privacidad + enum + cap + budget/source_ref/truncation checks para reports SP-077.

## Validation Performed
- py_compile script SP-077.
- suite unittest requerida (ver sección final del safepoint).

## Safety Constraints
- No OpenAI.
- No auto-switch.
- No write-back.
- Cap calls <=24 respetado.

## Known Limitations
- response_control todavía ausente en outputs reales observados.
- continuation repair no garantiza recuperación en truncation severa Pro.

## Future Extensions
- Multi-chunk chapters con reserve de continuation mayor.
- Heurística de reducción Pro con menor verbosity cuando usage se acerca a cap.

## Runtime Changes
- Script dev endurece assessment, metrics, coverage y decision fields.

## Write-back
- NO.

## Branch
- phase-1.3-ingestion-vaerl-hardening

## Next Suggested Phase
- Phase 1.3.M-b5c-4g — Larger DeepSeek E2E with Continuation in Multi-chunk Chapters
