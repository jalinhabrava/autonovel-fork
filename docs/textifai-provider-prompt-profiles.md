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

## Implementation Status

`SP-061` añade base provider-free:

- registry simple de perfiles;
- resolución por `provider + model + task`;
- overlay de prompt solo en `system_prompt`;
- validación heurística de densidad;
- integración dev-only opcional con `real_provider_dryrun.py` vía `--provider-profile`.

Todavía no se cablea al pipeline productivo de ingestion.

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
  "schema_strategy": "full_v2_with_density_reminder",
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
    "objects": "include all structurally relevant artifacts, tools, catalysts, weapons, keys, persistent props, and event-triggering props.",
    "events": "include all durable structural events, not only the final scene outcome.",
    "relations": "include protagonist-object, protagonist-place, protagonist-concept, object-event, authority/political, and magic/system relations when supported.",
    "unresolved_mentions": "include important unresolved actors, objects, concepts, or pronouns rather than silently dropping them.",
    "review": "keep uncertain identities in review or local candidate instead of promoting them."
  },
  "review_safety_policy": "do_not_promote_uncertain_identities",
  "validation_policy": "strict_json_and_density_check",
  "fallback": "retry_with_density_boost_or_larger_model"
}
```

## Current DeepSeek V4 Flash Profile

Perfil inicial implementado para:

- `provider = deepseek`
- `model_pattern = deepseek-v4-flash`
- `task = bootstrap_chapter_extraction`
- `default_max_output_tokens = 8192`
- `prompt_density_policy = high_recall_concise_facts`
- `validation_policy = strict_json_and_density_check`

Overlay actual fuerza:

- no comprimir extracción al resumen principal;
- no omitir secciones del schema;
- no omitir objetos/eventos/relaciones estructuralmente relevantes;
- usar `unresolved_mentions` en vez de borrar referencias inciertas;
- mantener review safety.

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

- `SP-062`: usar registry para un segundo dry-run optimizado DeepSeek `ch_002`.
- `SP-063`: comparar DeepSeek genérico vs DeepSeek perfilado.
- `SP-064`: evaluar fallback `deepseek-v4-pro` u OpenAI para capítulos difíciles.

Comparaciones objetivo:

- DeepSeek genérico vs DeepSeek optimizado.
- DeepSeek optimizado vs baseline manual ChatGPT.

Decisión posterior:

- usar DeepSeek Flash para extracción barata estándar;
- usar DeepSeek Pro/OpenAI para retries o capítulos complejos;
- aplicar fallback policy por calidad/coste.
