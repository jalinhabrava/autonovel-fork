# TextifAI Prompt Experiment Observability

## Product Value

Harness optimizado por provider/modelo necesita trazabilidad.
Score final solo no basta.
Hay que saber qué cambio de prompt produjo qué efecto, qué hipótesis probó cada variante y qué fallo ocurrió cuando run salió mal.

## Privacy Rule

No se commitean prompts privados ni outputs privados.
Sí se commitean:

- overlays genéricos sin texto de novela;
- hashes seguros;
- métricas;
- scores;
- failure modes;
- diff conceptual entre variantes;
- decisiones keep/mutate/discard/needs_repeat.

## Experiment Lifecycle

1. Define hypothesis.
2. Run matrix.
3. Classify results.
4. Assign failure modes.
5. Decide `keep`, `mutate`, `discard`, o `needs_repeat`.
6. Package profile o iterate.

## DeepSeek Observability Scope

`SP-071` formaliza observabilidad provider-free para matrices DeepSeek ya ejecutadas en `SP-067`, `SP-068`, `SP-069` y perfiles empaquetados en `SP-070`.

## Experiment Taxonomy

Cada variante debe poder registrarse con:

- `experiment_id`
- `provider_family`
- `model`
- `task`
- `chapter_id`
- `variant_id`
- `parent_variant_id`
- `variant_goal`
- `hypothesis`
- `prompt_change_type`
- `expected_effect`
- `risk`
- `result_summary`
- `failure_mode`
- `decision`

## Failure Mode Taxonomy

Baseline actual:

- `invalid_json_markdown`
- `invalid_json_extra_text`
- `invalid_json_truncated`
- `invalid_json_reasoning_leak`
- `invalid_json_unknown`
- `valid_json_wrong_shape`
- `valid_json_missing_required_sections`
- `valid_json_wrong_chapter`
- `valid_json_thin`
- `valid_json_low_objects`
- `valid_json_low_events`
- `valid_json_low_relations`
- `valid_json_zero_unresolved`
- `provider_empty_response`
- `provider_error`
- `validation_failed_missing_event_importance`
- `validation_failed_missing_relation_category`

## Variant Diff Reports

Toda matriz futura debe explicar:

- qué cambió conceptualmente;
- qué hipótesis probaba variante;
- target principal;
- riesgo;
- resultado observado;
- decisión.

## Future Matrix Requirements

Toda matriz futura debe producir:

- `variant diff report`
- `failure mode report`
- `decision report`
- `privacy-safe summary`

## Runtime Scope

- Sin provider calls en esta fase.
- Sin chunking.
- Sin write-back.
- Sin schema change productivo.

## Link with Provider Profiles

Perfiles empaquetados en `docs/textifai-provider-prompt-profiles.md` deben poder rastrearse hacia variantes origen y decisiones experimentales.
