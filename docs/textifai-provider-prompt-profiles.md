# TextifAI Provider Prompt Profiles

## Product Value

TextifAI no solo llama LLMs. TextifAI optimiza extracción por `provider + model + task`.

Valor producto:

- mejor calidad/coste;
- mayor fiabilidad JSON;
- densidad semántica calibrada;
- review safety estable;
- menor lock-in de vendor.

## Problem Observed

- `SP-060`: DeepSeek V4 Flash con prompt genérico devolvió JSON válido pero semánticamente fino.
- `SP-061`: se añadió registry + overlay de densidad provider-free.
- `SP-063`: ejecución real con `--provider-profile auto` aplicó profile, pero salida quedó no parseable JSON.

Conclusión: profile mecánico funciona; overlay previo era demasiado agresivo/discursivo para JSON reliability.

## SP-064 Compact Revision

Objetivo de revisión:

1. JSON validity first.
2. Density second.
3. Overlay corto e imperativo.
4. Cero contenido de obra específica.

Se mantiene perfil `deepseek-v4-flash:bootstrap_chapter_extraction:v1` con políticas explícitas:

- `json_reliability_policy = json_first_no_markdown_single_object`
- `prompt_density_policy = compact_high_recall`
- `overlay_style = compact_json_first`
- `default_max_output_tokens = 8192`

## Profile Shape (current)

```json
{
  "profile_id": "deepseek-v4-flash:bootstrap_chapter_extraction:v1",
  "provider": "deepseek",
  "model_pattern": "deepseek-v4-flash",
  "task": "bootstrap_chapter_extraction",
  "json_mode": true,
  "default_max_output_tokens": 8192,
  "json_reliability_policy": "json_first_no_markdown_single_object",
  "prompt_density_policy": "compact_high_recall",
  "overlay_style": "compact_json_first",
  "schema_strategy": "full_v2_with_density_reminder",
  "review_safety_policy": "do_not_promote_uncertain_identities",
  "validation_policy": "strict_json_and_density_check",
  "fallback": "retry_with_density_boost_or_larger_model"
}
```

## Compact Overlay (current)

```text
DeepSeek V4 Flash JSON reliability and extraction density:

Return exactly one valid JSON object. Do not use markdown.

Keep every required schema key:
work, chapters, characters, places, concepts, objects, events, relations, unresolved_mentions.

Do not compress the extraction into only the summary.

Include structurally relevant:
- objects/tools/artifacts/catalysts/weapons;
- durable events;
- evidence-backed relations;
- important unresolved mentions.

Keep facts concise.
Keep uncertain identities in review/local candidate.
Do not invent names.
```

## JSON Reliability vs Density Policy

Separación explícita:

- `json_reliability_policy`: obliga formato (`single JSON object`, `no markdown`).
- `prompt_density_policy`: empuja cobertura (`objects/events/relations/unresolved`) sin rehacer schema completo.

Regla producto: nunca sacrificar parseabilidad por densidad.

## Density Validation Role

El profile no “garantiza” densidad por sí solo. Flujo recomendado:

1. Prompt profile pide cobertura compacta.
2. Validación provider-free detecta salida fina o inválida.
3. Retry/fallback decide:
   - retry con overlay compacto;
   - retry con overlay más fuerte y JSON-safe;
   - subir a `deepseek-v4-pro`;
   - fallback a OpenAI;
   - o ajustar split/reduction.

## Non-goals

- no hardcode narrativo por obra;
- no cambios a schema productivo global;
- no chunking en esta fase;
- no llamadas provider en `SP-064`.

## Next Runtime Command (for SP-065)

```bash
uv run python scripts/dev/real_provider_dryrun.py \
  --prompt-file "$PROMPT_FILE" \
  --provider deepseek \
  --model deepseek-v4-flash \
  --output-root "/tmp/textifai_real_provider_dryrun_profiled" \
  --allow-provider-calls \
  --max-provider-requests 1 \
  --max-output-tokens 8192 \
  --response-format-json \
  --provider-profile auto \
  --no-write-back
```

## Future Implementation Plan

- `SP-065`: segunda llamada real única con overlay compacto.
- Comparar contra:
  - DeepSeek genérico `SP-060`;
  - DeepSeek perfilado previo `SP-063`;
  - baseline manual `SP-056`.
- Decidir:
  - mantener Flash con overlay compacto;
  - iterar profile;
  - o fallback a modelo más fuerte.
