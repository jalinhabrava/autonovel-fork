# TextifAI Provider Prompt Profiles

## Product Value

TextifAI no solo llama modelos. TextifAI optimiza cómo pedir extracción por `provider+model+task`.

Valor producto:

- mejor calidad por token;
- menor coste total;
- JSON reliability más estable;
- mejor review safety;
- flexibilidad multivendor sin lock-in fuerte.

Esto puede formar parte directa de propuesta de valor de planes de pago: extracción usable con menor coste y controles de calidad explícitos.

## Problem Observed

Con mismo contrato y mismo prompt capturado:

- baseline manual ChatGPT (`SP-056`) mantiene mayor densidad semántica;
- DeepSeek V4 Flash runtime devuelve JSON válido pero más comprimido;
- sin output-token budget suficiente, puede devolver salida vacía.

Conclusión: no basta “prompt genérico único para todos”. Se necesita perfil por provider/modelo.

## Proposed Profile Shape

```json
{
  "profile_id": "deepseek-v4-flash:bootstrap_chapter_extraction:v1",
  "provider": "deepseek",
  "model_pattern": "deepseek-v4-flash",
  "task": "bootstrap_chapter_extraction",
  "json_mode": true,
  "default_max_output_tokens": 8192,
  "prompt_density_policy": "high_recall_concise_facts",
  "schema_strategy": "full_v2_or_compact_v2",
  "must_include_sections": [
    "characters",
    "places",
    "concepts",
    "objects",
    "events",
    "relations",
    "unresolved_mentions"
  ],
  "minimum_density_targets": {
    "events": "all durable events, not fewer than chapter evidence supports",
    "relations": "all key protagonist/object/concept relations",
    "objects": "all structurally relevant artifacts/tools/catalysts"
  },
  "review_safety_policy": "do_not_promote_uncertain_identities",
  "validation_policy": "strict_json_and_density_check",
  "fallback": "retry_with_density_boost_or_larger_model"
}
```

## Provider-specific Examples

- `openai/gpt-*`: baseline fuerte, extracción rica, coste mayor.
- `deepseek-v4-flash`: barato, necesita budget y densidad explícita.
- `deepseek-v4-pro`: candidato más fuerte para capítulos difíciles, coste mayor que Flash.
- `lmstudio/local`: útil para privacidad/offline, requiere validación estricta y/o chunks más pequeños.

## Non-goals

- No hardcodear contenido narrativo de una obra.
- No crear reglas ad-hoc por novela.
- No aceptar salida semánticamente pobre solo por coste.
- No duplicar prompts completos por provider sin necesidad.

## Future Implementation Plan

- `SP-061`: registry provider prompt profiles (provider-free first).
- `SP-062`: perfil DeepSeek V4 Flash de densidad para extracción.
- `SP-063`: segundo dry-run real `ch_002` con perfil optimizado.

Comparaciones objetivo:

- DeepSeek genérico vs DeepSeek optimizado.
- DeepSeek optimizado vs baseline manual ChatGPT.

Decisión posterior:

- usar DeepSeek Flash para extracción barata estándar;
- usar DeepSeek Pro/OpenAI para retries o capítulos complejos;
- aplicar fallback policy por calidad/coste.
