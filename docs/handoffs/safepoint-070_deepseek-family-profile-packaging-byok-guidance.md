# Safepoint 070 — DeepSeek Family Profile Packaging + BYOK Guidance

## DeepSeek Family Profile Packaging + BYOK Guidance

## Product Reading

`SP-069` confirmó modelos visibles (`deepseek-v4-flash`, `deepseek-v4-pro`) y ausencia de reasoner en discovery. También confirmó que no existe un único model+variant ganador global. Lectura correcta: empaquetar perfiles por modelo dentro de DeepSeek-family, mantener BYOK explícito, añadir warnings/rerun guidance intra-modelo, sin routing automático.

## Scope

- Empaquetado provider-free de perfiles DeepSeek-family por modelo.
- Guidance BYOK por modelos habilitados.
- Warnings de thin output y gate de readiness e2e barato.
- Tests provider-free y fixtures esperados.

## Files Changed

- `textifai/import_review/provider_prompt_profiles.py`
- `textifai/import_review/deepseek_family_profiles.py`
- `tests/test_textifai_provider_prompt_profiles.py`
- `tests/test_textifai_deepseek_family_profiles.py`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_family_profiles_after_sp069.json`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_family_byok_guidance_after_sp069.json`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_family_thin_output_warnings_after_sp069.json`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_family_e2e_readiness_gate_after_sp069.json`
- `docs/textifai-provider-prompt-profiles.md`
- `docs/handoffs/safepoint-070_deepseek-family-profile-packaging-byok-guidance.md`

## SP069 Evidence

- Discovery visible: `deepseek-v4-flash`, `deepseek-v4-pro`
- Reasoner: no visible en `SP-069`
- Best `ch_002`: Flash + `family_variant_2_oer_focus` (`score=26.5`)
- Best `ch_003`: Pro + `family_variant_3_balanced_kb` (`score=25.0`)
- Common shared model+variant viability: `false`

## Packaged Flash Profile

- `profile_id`: `deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1`
- Base: `family_variant_2_oer_focus`
- Política: JSON-first + énfasis en objects/events/relations/unresolved_mentions.

## Packaged Pro Profile

- `profile_id`: `deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1`
- Base: `family_variant_3_balanced_kb`
- Política: JSON-first + cobertura balanceada tipo knowledge-base.

## Reasoner Status

- `discovery_status`: `not_visible_in_sp069`
- `profile_status`: `not_packaged`
- `reason`: `not available in current model discovery`

## BYOK Guidance

- Usa solo modelos habilitados por usuario.
- Si solo Flash habilitado: usar profile Flash + warnings + rerun same-model.
- Si solo Pro habilitado: usar profile Pro + warnings + rerun same-model.
- Si ambos habilitados: comparación informativa permitida, sin auto-switch invisible.

## Thin Output Warnings

Policy codes:

- `low_density_score`
- `zero_unresolved_mentions_in_ambiguous_context`
- `low_objects_count`
- `low_events_count`
- `low_relations_count`
- `valid_json_but_thin`
- `model_profile_experimental`

## E2E Readiness Gate

Resultado empaquetado:

- `deepseek_family_usable_for_low_cost_e2e_preflight = true`
- `production_quality_claim = false`
- `requires_review_warnings = true`
- `requires_output_validation = true`
- `reasoner_profile_available = false`
- `common_family_profile_viable = false`
- `per_model_profiles_required = true`
- `assessment = deepseek_family_profiles_packaged_for_e2e_preflight`

## What This Enables

- Gestión DeepSeek-family usable en preflight e2e barato BYOK.
- Selección explícita de profile por modelo DeepSeek habilitado.
- Warnings consistentes para salidas válidas-pero-thin.
- Guidance de rerun intra-modelo sin routing global.

## What It Does Not Yet Do

- No routing automático global provider/model.
- No auto-switch invisible Flash↔Pro ni DeepSeek↔OpenAI.
- No profile reasoner por falta de disponibilidad en discovery.
- No chunking/reduction todavía.

## Tests Added / Updated

- `tests/test_textifai_provider_prompt_profiles.py` (expectativas SP-070 para resolución de profile Flash empaquetado).
- `tests/test_textifai_deepseek_family_profiles.py` (nuevo):
  - existencia profiles Flash/Pro;
  - estado reasoner no empaquetado;
  - BYOK guidance por enabled models;
  - thin warnings;
  - readiness gate;
  - parse de fixtures SP-070.

## Validation Performed

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
- Commit de `/tmp`: NO
- Commit de prompts/outputs privados: NO

## Known Limitations

- Evidence de score sigue basada en pocos capítulos (SP-069).
- Heurística de thin warnings no reemplaza revisión humana.
- Reasoner no visible en discovery actual.

## Future Extensions

- Añadir profiles alternativos same-model para rerun dirigido.
- Extender señales de thin output con métricas de consistencia semántica.
- Revalidar tras chunking/reduction preflight.

## Runtime Changes

- Solo helpers de profile/guidance provider-free.
- Sin cambios de schema productivo.

## Provider Calls

- NO.

## Write-back

- NO.

## Branch

- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

`Phase 1.3.M-b5c-4a — Chunking/Reduction Preflight with DeepSeek Family Harness Available`
