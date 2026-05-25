# TextifAI Provider Prompt Profiles

## Product Reading

TextifAI es BYOK: usuario habilita provider/modelo y TextifAI optimiza harness para esa elección.
No hay routing automático global en esta fase.

Tras `SP-069`, DeepSeek-family queda usable para preflight e2e barato con perfiles por modelo:

- `deepseek-v4-flash` visible y probado.
- `deepseek-v4-pro` visible y probado.
- `deepseek-reasoner` no visible en discovery de `SP-069`; no empaquetado todavía.

## DeepSeek Family Packaging (SP-070)

### Flash profile v1

- `profile_id`: `deepseek-v4-flash:bootstrap_chapter_extraction:oer_focus_v1`
- Base: `SP-069 family_variant_2_oer_focus`
- Mejor evidencia observada: `ch_002` (`score=26.5`)
- Política: foco fuerte en `objects/events/relations/unresolved_mentions` con JSON-first.

### Pro profile v1

- `profile_id`: `deepseek-v4-pro:bootstrap_chapter_extraction:balanced_kb_v1`
- Base: `SP-069 family_variant_3_balanced_kb`
- Mejor evidencia observada: `ch_003` (`score=25.0`)
- Política: cobertura equilibrada de knowledge-base con JSON-first.

### Reasoner status

- `model_id`: `deepseek-reasoner`
- `discovery_status`: `not_visible_in_sp069`
- `profile_status`: `not_packaged`
- `reason`: `not available in current model discovery`

## BYOK In-Model Guidance

Si usuario habilita:

- Solo `deepseek-v4-flash`:
  - usar `oer_focus_v1`;
  - mostrar warning de thin output cuando aplique;
  - sugerir rerun en mismo modelo si existe perfil alternativo del mismo modelo.
- Solo `deepseek-v4-pro`:
  - usar `balanced_kb_v1`;
  - mostrar warning de thin output;
  - no asumir superioridad absoluta frente a Flash.
- Ambos modelos:
  - mostrar guidance comparativo informativo;
  - no auto-switch invisible.

## Thin Output Warnings

Códigos recomendados:

- `low_density_score`
- `zero_unresolved_mentions_in_ambiguous_context`
- `low_objects_count`
- `low_events_count`
- `low_relations_count`
- `valid_json_but_thin`
- `model_profile_experimental`

## E2E Readiness Gate

`deepseek_family_e2e_readiness_gate_after_sp069.json` declara:

- `deepseek_family_usable_for_low_cost_e2e_preflight = true`
- `production_quality_claim = false`
- `requires_review_warnings = true`
- `requires_output_validation = true`
- `reasoner_profile_available = false`
- `common_family_profile_viable = false`
- `per_model_profiles_required = true`

## Runtime Scope and Non-goals

- Sin llamadas provider/API en `SP-070`.
- Sin chunking.
- Sin write-back.
- Sin routing automático global.
- Sin cambios de schema productivo.

## Next Suggested Phase

`Phase 1.3.M-b5c-4a — Chunking/Reduction Preflight with DeepSeek Family Harness Available`
