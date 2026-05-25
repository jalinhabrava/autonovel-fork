# Safepoint 071 — Prompt Experiment Observability + Variant Diff Reports

## Prompt Experiment Observability + Variant Diff Reports

## Product Reading

`SP-070` dejó perfiles DeepSeek-family empaquetados y BYOK guidance, pero faltaba observabilidad formal de experimentos. Sin eso, futuras matrices quedan opacas: cuesta explicar qué cambió, qué hipótesis se probó, qué failure mode ocurrió y por qué una variante se empaquetó o se descartó.

## Scope

- Helper provider-free para taxonomía de experimentos.
- Taxonomía de failure modes.
- Variant diff report y variant decision report.
- Tests provider-free, fixtures y docs.

## Files Changed

- `textifai/import_review/prompt_experiment_observability.py`
- `tests/test_textifai_prompt_experiment_observability.py`
- `tests/fixtures/textifai/prompt_experiments/expected/deepseek_prompt_experiment_taxonomy_after_sp070.json`
- `tests/fixtures/textifai/prompt_experiments/expected/deepseek_variant_diff_report_after_sp070.json`
- `tests/fixtures/textifai/prompt_experiments/expected/deepseek_failure_mode_taxonomy_after_sp070.json`
- `tests/fixtures/textifai/prompt_experiments/expected/deepseek_variant_decision_report_after_sp070.json`
- `docs/textifai-prompt-experiment-observability.md`
- `docs/handoffs/safepoint-071_prompt-experiment-observability-variant-diff-reports.md`
- `docs/textifai-provider-prompt-profiles.md`

## Why This Matters

Harnesses por provider/modelo son producto. Producto exige trazabilidad auditable: cambio conceptual, hipótesis, efecto observado, failure mode y decisión final.

## Experiment Taxonomy

Registro formal con:

- identidad (`experiment_id`, `variant_id`, `parent_variant_id`)
- objetivo (`variant_goal`, `hypothesis`, `expected_effect`, `risk`)
- tipos de cambio (`prompt_change_type`)
- resultado seguro (`result_summary`, `failure_mode`, `decision`)

## Failure Mode Taxonomy

Se añadieron clases de fallo para JSON inválido, shape incorrecto, thin output, secciones ausentes, chapter incorrecto, errores provider y fallos de validación de schema auxiliar.

## Variant Diff Reports

Se registraron diffs conceptuales para variantes DeepSeek relevantes:

- `family_variant_2_oer_focus`
- `family_variant_3_balanced_kb`
- `variant_g_combined_best`
- `variant_l_balanced_final_candidate`

## Variant Decision Report

Se separaron variantes en:

- packaged
- kept for future mutation
- discarded
- requiring repeat

## Privacy Rules

- Sin prompts privados commiteados.
- Sin outputs privados commiteados.
- Solo overlays genéricos, métricas seguras, hashes, failure modes y decisiones.

## Future Matrix Requirements

Toda matriz futura debe producir:

- diff report;
- failure mode report;
- decision report;
- privacy-safe summary.

## Tests Added / Updated

- `tests/test_textifai_prompt_experiment_observability.py` nuevo.
- `tests/test_textifai_real_provider_dryrun_guards.py` con parse de reportes SP-071.
- `docs/textifai-provider-prompt-profiles.md` enlazado con observabilidad.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_prompt_experiment_observability`
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_deepseek_family_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- `git status --short`
- `git diff --stat`

## Safety Constraints

- Provider calls: NO
- Red: NO
- Chunking: NO
- Write-back: NO
- `/tmp`: no commit

## Known Limitations

- Reports derivan de métricas y decisiones ya existentes; no reejecutan matrices.
- Failure classification sigue heurística.
- No hay integración runtime automática todavía.

## Future Extensions

- Auto-emisión de observability reports desde futuras matrices.
- Mapping más fino entre failure hints runtime y taxonomy final.
- Correlación temporal entre packaged profiles y variantes origen.

## Runtime Changes

- Solo helpers provider-free de observabilidad.

## Provider Calls

- NO.

## Write-back

- NO.

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.M-b5c-4a — Chunking/Reduction Preflight with DeepSeek Family Harness and Prompt Experiment Observability Available`
