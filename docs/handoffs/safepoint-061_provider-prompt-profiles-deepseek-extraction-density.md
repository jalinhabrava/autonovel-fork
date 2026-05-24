# Provider Prompt Profiles + DeepSeek Extraction Density

## Product Reading
- `SP-060` demostró que DeepSeek V4 Flash cumple shape mínimo pero queda corto en densidad semántica.
- Necesitamos infraestructura para expresar presupuesto, overlay y validación por provider/modelo/task.
- Esta fase implementa base provider-free de esa infraestructura.

## Scope
- Crear registry de perfiles.
- Añadir perfil inicial `deepseek-v4-flash:bootstrap_chapter_extraction:v1`.
- Añadir overlay de densidad.
- Añadir validación heurística de densidad.
- Añadir integración dev-only opcional al dry-run script.

## Files Changed
- `textifai/import_review/provider_prompt_profiles.py`
- `tests/test_textifai_provider_prompt_profiles.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_v4_flash_bootstrap_chapter_extraction_profile.json`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/deepseek_v4_flash_density_prompt_overlay.md`
- `tests/fixtures/textifai/provider_prompt_profiles/expected/provider_prompt_profiles_registry_report.json`
- `docs/textifai-provider-prompt-profiles.md`
- `docs/handoffs/safepoint-061_provider-prompt-profiles-deepseek-extraction-density.md`
- `scripts/dev/real_provider_dryrun.py`

## Provider Prompt Profile Registry
- Registry simple con `ProviderPromptProfile` dataclass.
- Helpers:
  - `list_provider_prompt_profiles()`
  - `get_provider_prompt_profile(provider, model, task)`
  - `apply_provider_prompt_profile(system_prompt, user_prompt, profile)`
  - `summarize_provider_prompt_profile(profile)`
  - `validate_extraction_density(payload, profile)`

## DeepSeek V4 Flash Profile
- `profile_id = deepseek-v4-flash:bootstrap_chapter_extraction:v1`
- `provider = deepseek`
- `model_pattern = deepseek-v4-flash`
- `task = bootstrap_chapter_extraction`
- `json_mode = true`
- `default_max_output_tokens = 8192`
- `prompt_density_policy = high_recall_concise_facts`
- `validation_policy = strict_json_and_density_check`

## Prompt Overlay
- Overlay compacto, provider-aware, obra-agnóstico.
- Refuerza cobertura de objetos/eventos/relaciones/unresolved y review safety.
- No introduce nombres privados de novela.

## Prompt Augmentation
- Overlay se añade al `system_prompt` bajo `## Provider Profile Overlay`.
- No toca `user_prompt`.
- Idempotente: no duplica overlay si ya existe.

## Density Validation
- Helper provider-free valida:
  - secciones requeridas;
  - presencia de `event_importance` y `relation_category` cuando aplica;
  - warnings heurísticos como `low_relation_count`, `low_object_count`, `empty_unresolved_mentions`.
- No hardcodea counts fijos universales ni contenido narrativo de obra.

## Dry-run Script Integration
- Integración dev-only implementada en `scripts/dev/real_provider_dryrun.py`:
  - `--provider-profile none|auto|PROFILE_ID`
- Default `none` preserva comportamiento previo.
- `auto` resuelve perfil por provider/model/task.
- Manifest registra:
  - `provider_profile_requested`
  - `provider_profile_id`
  - `provider_profile_applied`
- No se hicieron llamadas provider en esta fase.

## Product Value
- Infraestructura explícita para calidad/coste por provider.
- Base para retry/fallback policy futura.
- Paso directo hacia diferenciación de producto por tuning provider-aware.

## What This Enables
- Segundo dry-run DeepSeek con overlay de densidad.
- Budget por perfil y validación por perfil.
- Comparación formal genérico vs perfilado.

## What It Does Not Yet Do
- No cablea perfiles al pipeline productivo de ingestion.
- No optimiza todavía el prompt DeepSeek en runtime real.
- No ejecuta nueva llamada provider.

## Provider-free Guarantee
- Todo validado con tests locales.
- Sin red.
- Sin API.
- Sin prompts privados ni outputs privados versionados.

## Tests Added / Updated
- `tests/test_textifai_provider_prompt_profiles.py`
- `tests/test_textifai_real_provider_dryrun_guards.py` actualizado para `--provider-profile auto`

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `uv run python -m unittest -v tests.test_textifai_provider_onboarding`

## Data Written
- Solo código/tests/docs/fixtures esperados.
- Nada en `runs/**`, `vault/**`, `.env`, `/tmp` del repo.

## Safety Constraints
- No provider calls.
- No write-back.
- No chunking.

## Known Limitations
- Registry tiene un único perfil inicial.
- Validación de densidad es heurística y no semántica profunda.
- Falta integración productiva.

## Future Extensions
- `SP-062`: segundo dry-run DeepSeek `ch_002` con profile aplicado.
- `SP-063`: fallback/retry policy por provider/model.

## Runtime Changes
- Helpers de perfiles + integración dev-only en dry-run script.

## Provider Calls
- NO.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3f — Optimized DeepSeek ch_002 Dry-run with Provider Profile`
