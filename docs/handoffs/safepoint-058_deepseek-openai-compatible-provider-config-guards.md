# DeepSeek OpenAI-Compatible Provider Config + Guards

## Product Reading
- `safepoint-055`, `safepoint-056`, `safepoint-057` validaron contrato de extracción con `CANONICAL_ENTITY_MAP` poblado en tres perfiles narrativos.
- Gate quedó en `contract_ready_for_chunking_preflight`.
- Todavía faltaba preparar camino runtime provider real con riesgo/coste controlado.
- Esta fase prepara provider/config/guards sin ejecutar llamadas reales.

## Scope
- Añadir soporte `deepseek` como provider OpenAI-compatible sin duplicar lógica de payload/parsing.
- Mantener compatibilidad actual (`openai_compatible`, `openai`, `anthropic`, `lmstudio`, `ollama`).
- Añadir tests provider-free para alias/config/request-building/response_format.
- Añadir notas de guardrails para próxima fase dry-run real.

## Files Changed
- `providers/text_provider.py`
- `textifai/provider_onboarding.py`
- `tests/test_text_provider.py`
- `tests/test_textifai_provider_onboarding.py`

## Provider Architecture
- Se reutiliza `OpenAICompatibleTextProvider` para `deepseek`.
- No se crea `DeepSeekProvider` dedicado.
- `deepseek` entra por alias + registry + config error checks.

## DeepSeek Alias / Config
- Alias nuevo: `deepseek` en `PROVIDER_ALIASES`.
- Registry nuevo: `deepseek -> OpenAICompatibleTextProvider(provider_name="deepseek")`.
- API key env: `DEEPSEEK_API_KEY`.
- Base URL env: `AUTONOVEL_DEEPSEEK_API_BASE_URL`.
- Base URL default: `https://api.deepseek.com`.

## OpenAI-Compatible Reuse
- DeepSeek usa endpoint `/chat/completions` y formato payload OpenAI-compatible ya existente.
- Se preserva normalización de respuesta `choices[0].message.content`.
- `openai_compatible` no cambia comportamiento.

## Environment Variables
- Runtime bootstrap:
  - `AUTONOVEL_BOOTSTRAP_PROVIDER=deepseek`
  - `AUTONOVEL_BOOTSTRAP_MODEL=deepseek-v4-flash` (o `deepseek-v4-pro`)
  - `DEEPSEEK_API_KEY=...`
  - `AUTONOVEL_DEEPSEEK_API_BASE_URL=https://api.deepseek.com` (opcional override)
- Onboarding:
  - `ProviderConfiguration(provider_choice="deepseek", ...)` ya soportado.

## JSON Response Format Support
- `response_format={"type":"json_object"}` se conserva en payload OpenAI-compatible.
- Cubierto por test provider-free DeepSeek con `httpx` fake.

## Cost / Safety Guards
- Esta fase no ejecuta dry-run real ni llamadas de red.
- Guardrails definidos para fase siguiente:
  - `--allow-provider-calls` obligatorio
  - `--max-provider-requests 1`
  - `--no-write-back` por defecto
  - salida por defecto a `/tmp/textifai_real_provider_dryrun`
  - trazas completas solo con flag explícito (`--save-trace`)
  - opción de redacción de prompt/source antes de persistir
  - no commitear prompts/outputs privados salvo fixture aprobada

## Direct OpenAI Path Limitation
- Sigue existiendo camino directo OpenAI `/responses` en `structured_bootstrap_v1.py` fuera de provider genérico.
- Esta fase no lo reescribe.
- Primera prueba runtime real recomendada debe usar chapter extraction vía `provider.generate`, no global normalization real.

## Provider-free Guarantee
- Tests nuevos usan `patch.dict(os.environ, ...)` y `httpx` fake.
- Sin secrets reales.
- Sin llamadas red reales.
- Sin escritura en `runs/**` ni `vault/**`.

## Tests Added / Updated
- `tests/test_text_provider.py`
  - `test_deepseek_provider_uses_openai_compatible_payload_and_json_response_format`
  - `test_deepseek_missing_api_key_reports_config_error_without_network`
  - `test_deepseek_provider_name_can_come_from_bootstrap_provider_env`
  - update smoke aliases para incluir `deepseek`
- `tests/test_textifai_provider_onboarding.py`
  - `test_configure_provider_supports_deepseek_configuration`
  - `test_evaluate_provider_readiness_reports_deepseek_missing_key`

## Validation Performed
- `uv run python -m unittest -v tests.test_text_provider`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_populated_map_ch003_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_populated_map_ch002_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_real_bootstrap_populated_map_chatgpt_response_audit`
- `uv run python -m unittest -v tests.test_textifai_structured_bootstrap_v1.StructuredBootstrapV1Tests.test_run_structured_bootstrap_v1_writes_json_artifacts`
- `uv run python scripts/textifai.py provider --help`

## Data Written
- Solo código/tests/handoff.
- No fixtures privados nuevos.
- No provider outputs reales.

## Safety Constraints
- Sin llamadas provider reales.
- Sin red runtime real para extracción.
- Sin write-back.
- Sin cambio de contrato semántico de extracción.

## Known Limitations
- Dry-run real con guard flags aún no implementado como comando dedicado.
- Snapshot dinámico de modelos sigue especializado para `openai` en `provider_snapshot`.
- Camino directo OpenAI `/responses` sigue aparte.

## Future Extensions
- Añadir comando dry-run real controlado con guardrails explícitos.
- Añadir reporte estimado de coste/tokens sin persistencia sensible por defecto.
- Añadir modo comparación controlada DeepSeek vs OpenAI para `ch_002`.

## Runtime Changes
- Solo resolución/config de provider:
  - alias `deepseek`
  - env var mapping DeepSeek
  - onboarding DeepSeek

## Provider Calls
- NO.

## Write-back
- NO.

## Branch
- `phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
- `Phase 1.3.M-b5c-3c — Real Provider Dry-run on ch_002 with DeepSeek/OpenAI-compatible`
