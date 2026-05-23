# DeepSeek Real Output Audit + Provider Profiles + Token Guard

## Product Reading
- `SP-059` habilitó dry-run real con guards.
- Corrida real observada en `/tmp` confirmó que DeepSeek puede devolver JSON válido para `ch_002` con token budget suficiente.
- Diferencia principal vs baseline manual: menor densidad semántica, no fallo estructural del contrato.
- Oportunidad de producto: perfiles de prompt/presupuesto/validación por provider/modelo.

## Scope
- Auditar output real observado (sin commitear respuesta privada).
- Endurecer guard de output tokens en `real_provider_dryrun.py`.
- Generar reportes commiteables (resumen/compare/issues/oportunidad) sin texto privado.
- Definir base documental de `Provider Prompt Profiles`.

## Files Changed
- `scripts/dev/real_provider_dryrun.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_runtime_summary_after_sp059.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_vs_sp056_baseline_report.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/deepseek_ch002_runtime_issue_report.json`
- `tests/fixtures/textifai/real_provider_dryrun/expected/provider_prompt_profiles_product_opportunity_report.json`
- `docs/textifai-provider-prompt-profiles.md`
- `docs/handoffs/safepoint-060_deepseek-real-output-audit-provider-profiles-token-guard.md`

## Real Provider Run Observed
- Fuente observada (externa a repo):
  - `/tmp/textifai_real_provider_dryrun/20260523T104411Z/dryrun_manifest.json`
  - `/tmp/textifai_real_provider_dryrun/20260523T104411Z/validation_report.json`
  - `/tmp/textifai_real_provider_dryrun/20260523T104411Z/provider_response.json`
- Resultado observado:
  - provider/model: `deepseek` / `deepseek-v4-flash`
  - `response_text_chars`: `5551`
  - validación mínima: `ok=true`, parseable JSON, `chapter_id=ch_002`

## Output-token Issue
- Primera corrida histórica sin budget explícito devolvió output vacío.
- Corrida con `--max-output-tokens 8192` devolvió JSON parseable válido.
- Conclusión: token budget no puede quedar implícito en llamadas reales de este flujo.

## Token Guard / Default
- Script ahora fuerza política explícita:
  - `max_output_tokens > 0` obligatorio;
  - si no se pasa flag, usa default seguro `8192` para este task;
  - manifest guarda:
    - `max_output_tokens`
    - `max_output_tokens_source` (`default|user_provided`)

## Runtime JSON Validation
- Runtime observado cumple shape mínimo v2:
  - `work`, `chapters`, `chapter_id == ch_002`, `objects`, `events`, `relations`.
  - `event_importance` presente.
  - `relation_category` presente.

## Comparison vs SP056
- Baseline manual: `chatgpt_response_bootstrap_chapter_extraction_ja_ch_002_populated_map_after_sp055`.
- DeepSeek runtime: JSON válido, pero cobertura menor.
- Conteos comparados (runtime vs baseline):
  - characters: `3 vs 4`
  - places: `1 vs 3`
  - concepts: `4 vs 4`
  - objects: `2 vs 4`
  - events: `2 vs 5`
  - relations: `1 vs 7`
  - unresolved_mentions: `0 vs 4`
- Assessment: `runtime_json_valid_but_semantically_thin`.

## Semantic Density Assessment
- Fortaleza: contrato estructural mínimo preservado.
- Debilidad: extracción comprimida en relaciones/eventos/objetos y menciones no resueltas.
- Implicación: requiere profile de densidad por provider/modelo para ser usable y barato.

## Provider Prompt Profiles Product Value
- Valor negocio:
  - optimizar calidad/coste por provider;
  - diferenciar tiers de producto;
  - bajar lock-in de vendor.
- Valor técnico:
  - budget por perfil;
  - instrucciones JSON por perfil;
  - validación de densidad;
  - fallback/retry policy.

## Provider Prompt Profiles Proposed Shape
- Definido en `docs/textifai-provider-prompt-profiles.md`.
- Ejemplo central:
  - `profile_id = deepseek-v4-flash:bootstrap_chapter_extraction:v1`
  - `default_max_output_tokens = 8192`
  - `prompt_density_policy = high_recall_concise_facts`
  - `validation_policy = strict_json_and_density_check`

## What Worked
- Wrapper OpenAI-compatible con DeepSeek funcionó.
- JSON parseable y shape mínimo v2 confirmado.
- Guard/token budget y reporting mejorados.

## What Stayed Weak
- Densidad semántica menor frente a baseline manual.
- Solo un provider/modelo y un capítulo auditados en runtime.
- No hay diff semántico automático aún.

## Provider Wrapper Result
- `OpenAICompatibleTextProvider` + `deepseek` alias: técnicamente operativo.
- Problema principal no es parseo ni contrato mínimo; es calibración de perfil.

## Data Written
- Solo código/tests/docs/reportes agregados.
- Sin outputs privados de `/tmp` en repo.

## Privacy / Non-committed Output
- `provider_response.json` y prompt capture permanecen fuera del repo (`/tmp`).
- Reportes versionados contienen solo métricas y assessment resumido.

## Tests Added / Updated
- `tests/test_textifai_real_provider_dryrun_guards.py`:
  - default token budget;
  - user-provided token budget;
  - invalid token budget (0/-1) abort;
  - manifest con token metadata;
  - parse/privacy checks de reportes esperados.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_populated_map_ch002_chatgpt_response_audit`
- `git status --short`
- `git diff --stat`

## Safety Constraints
- Sin nuevas llamadas provider/API en esta fase.
- Sin red en fase de implementación/validación.
- Sin write-back.
- Sin chunking.

## Known Limitations
- No se implementó aún profile runtime integrado al prompt builder productivo.
- No hay evaluación semántica profunda automática aún.
- Audit runtime actual sigue siendo muestra única (`ch_002`, DeepSeek Flash).

## Future Extensions
- `SP-061`: registry de provider prompt profiles.
- `SP-062`: perfil DeepSeek V4 Flash de densidad para extracción.
- `SP-063`: segundo dry-run DeepSeek `ch_002` con perfil optimizado y comparación formal.

## Runtime Changes
- Guard/default de token budget en script dev-only.
- Reportes y documentación de base para provider profiles.

## Provider Calls
- NO nuevas en esta fase (solo observación de corrida previa en `/tmp`).

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3e — Provider Prompt Profiles Implementation: DeepSeek Extraction Density`
