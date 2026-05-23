# Real Provider Dry-run ch_002 DeepSeek

## Product Reading
- `safepoint-058` dejó DeepSeek integrado como OpenAI-compatible sin duplicar lógica.
- Faltaba probar camino runtime real mínimo con guardrails explícitos.
- Objetivo de esta fase: habilitar dry-run seguro y barato para `ch_002`, sin tocar prompt/schema ni chunking.

## Scope
- Crear script dev-only para una llamada runtime controlada.
- Añadir guards obligatorios para evitar llamadas accidentales.
- Validar JSON parseable y shape mínimo de contrato v2 `ch_002`.
- Añadir tests provider-free del flujo y guardrails.
- No guardar prompts/outputs privados dentro del repo.

## Files Changed
- `scripts/dev/real_provider_dryrun.py`
- `tests/test_textifai_real_provider_dryrun_guards.py`

## Dry-run Script
- Script nuevo: `scripts/dev/real_provider_dryrun.py`
- Entrada principal:
  - `--prompt-file`
  - `--provider deepseek|openai|openai_compatible`
  - `--model`
  - `--output-root` (default `/tmp/textifai_real_provider_dryrun`)
  - `--allow-provider-calls`
  - `--max-provider-requests`
  - `--response-format-json`
  - `--no-write-back`
  - `--save-trace`
  - `--redact-prompts`

## Safety Guards
- Sin `--allow-provider-calls` aborta antes de crear provider.
- `--max-provider-requests` debe ser exactamente `1`.
- `--no-write-back` debe permanecer habilitado.
- Si falta prompt file, aborta.
- Si falta configuración provider (`DEEPSEEK_API_KEY` para deepseek), aborta.
- Por defecto no guarda prompt completo.
- No imprime secrets.

## Prompt Used
- Objetivo configurado para:
  - `/tmp/textifai_prompt_capture_jp_populated_map_after_sp053/20260522T163323Z/request_003_bootstrap_chapter_extraction_ch_002.md`
- Parser implementado para extraer:
  - bloque `## System`
  - bloque `### Message 1`

## Provider / Model
- Provider esperado para ejecución real de esta fase: `deepseek`
- Modelo esperado: `deepseek-v4-flash`
- `response_format={"type":"json_object"}` si se usa `--response-format-json`

## Real Provider Call Status
- `not_executed_missing_key`
- Motivo observado en entorno de validación:
  - `DEEPSEEK_API_KEY` no presente.
  - además prompt target no estaba presente en ruta `/tmp` indicada.

## Output Directory
- Default seguro:
  - `/tmp/textifai_real_provider_dryrun/<timestamp>/`
- Artefactos esperados:
  - `dryrun_manifest.json`
  - `provider_response_raw.txt`
  - `provider_response.json` (si parseable)
  - `validation_report.json`
  - `prompt_trace.json` solo con `--save-trace`

## JSON Validation Result
- Validador implementado verifica:
  - top-level `work`
  - top-level `chapters`
  - primer capítulo `chapter_id == ch_002`
  - presencia de `objects`, `events`, `relations`
  - al menos un `event_importance`
  - al menos un `relation_category`
- En esta fase no hubo resultado runtime real por falta de key/prompt local.

## Comparison Readiness vs SP056
- Flujo preparado para comparar salida runtime contra baseline manual `SP-056` sin tocar repo:
  - output en `/tmp`
  - validación estructural automática
  - manifest con metadata para contraste

## Provider-free Tests
- Nuevo suite: `tests/test_textifai_real_provider_dryrun_guards.py`
- Cubre:
  - aborta sin `--allow-provider-calls`
  - aborta si `--max-provider-requests != 1`
  - aborta si prompt no existe
  - parser markdown extrae system/user
  - fake provider genera manifest/raw/json/validation
  - `response_format_json` llega al request
  - output no parseable marca validación fallida
  - no imprime secrets

## Real Call Metadata
- No aplica en esta fase por `not_executed_missing_key`.
- No hubo request id, tokens ni latencia runtime real.

## Data Written
- Código/tests en repo.
- Sin datos privados de prompt/output runtime en repo.
- Sin escritura en `runs/**` ni `vault/**`.

## Safety Constraints
- No chunking.
- No write-back.
- No merge/promote/canon mutation.
- No llamada real sin flags y límites.

## Known Limitations
- Ejecución real depende de key y prompt capture local en `/tmp`.
- Script valida shape mínimo; no compara semántica profunda automáticamente.

## Future Extensions
- Añadir diff automático contra fixture `SP-056` con reporte compacto.
- Añadir opción de costo estimado por token antes de llamar provider.

## Runtime Changes
- Dev dry-run tooling only.
- Sin cambio de contrato semántico ni pipeline productivo.

## Provider Calls
- NO.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3d — Compare real provider output vs SP056 baseline and decide chunking preflight entry`
