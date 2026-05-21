# Retention Review Policy

## Purpose

TextifAI usa señales de retención para convertir dudas semánticas en decisiones editoriales asistidas. La cola no debe limpiar agresivamente ni resolver identidad de forma silenciosa: debe explicar evidencia, proponer candidatos y dejar la decisión final al autor/editor.

## Core Principles

- No auto-promotion: una mención omitida no se convierte en primary por defecto.
- No auto-merge: un candidato probable no se fusiona automáticamente.
- Candidate guessing is advisory: candidatos, scores y razones solo preparan revisión humana.
- Preserve roles/titles/descriptors: roles, títulos y descriptores con evidencia son información semántica revisable.
- Pronouns should not become strong primaries: pronombres quedan suprimidos o con evidencia insuficiente, nunca como primary fuerte.
- Durable omitted entities should surface review signals: entidades durables omitidas deben generar señal si tienen peso narrativo.
- Ephemeral/noise mentions stay suppressed: menciones episódicas o ruido no deben inflar la cola salvo evidencia estructural.
- Language-agnostic by design: ejemplos de tests no son reglas universales de lengua.

## Recommended Actions

### `review_merge_or_alias`

- Cuándo: hay candidato canonical conservador por alias/source mention/overlap.
- Evidence esperado: surface, chapter refs, source mentions y reason del candidato.
- `candidate_entities`: no vacío, con score/reason/confidence bucket si existe.
- Severity sugerida: `medium`; `high` solo si hay riesgo fuerte de contaminación canonical.
- Ejemplo conceptual: `Mara` apunta a `Mara Elian`.
- Futuro botón UI: Merge o Mark as alias.

### `review_create_primary`

- Cuándo: entidad durable con evidencia suficiente no tiene primary claro.
- Evidence esperado: key facts, source mentions, chapter refs y razón de descarte upstream.
- `candidate_entities`: vacío o sin candidato claro.
- Severity sugerida: `medium`.
- Ejemplo conceptual: `brújula de plata` como objeto persistente omitido.
- Futuro botón UI: Promote to primary.

### `review_keep_secondary`

- Cuándo: mención con peso moderado no justifica primary pero tampoco parece ruido.
- Evidence esperado: menciones y capítulo donde aparece.
- `candidate_entities`: opcional.
- Severity sugerida: `low`.
- Ejemplo conceptual: elemento local recurrente sin rol estructural claro.
- Futuro botón UI: Keep secondary.

### `review_reject_noise`

- Cuándo: surface parece ruido, descriptor episódico o extracción débil.
- Evidence esperado: razón de supresión o baja evidencia.
- `candidate_entities`: vacío.
- Severity sugerida: `suppressed` o `low` si se expone.
- Ejemplo conceptual: mención única sin peso narrativo.
- Futuro botón UI: Reject noise.

### `review_insufficient_evidence`

- Cuándo: hay duda real pero falta evidencia para recomendar merge, primary o secondary.
- Evidence esperado: surface, confianza baja y razón de insuficiencia.
- `candidate_entities`: vacío o weak candidates.
- Severity sugerida: `low`.
- Ejemplo conceptual: surface ambigua sin overlaps suficientes.
- Futuro botón UI: Keep secondary o Reject noise.

### `review_attach_role_or_title`

- Cuándo: descriptor, título o rol apunta a entidad existente pero no debe ser primary separado.
- Para surfaces absorbidas como alias/source mention, emitir solo si `surface_type`/`semantic_value` indica título/rol y existe candidato canonical claro.
- Evidence esperado: surface, candidate entity, facts asociados y chapter refs.
- `candidate_entities`: candidato probable.
- Severity sugerida: `medium`; `high` si el descriptor contiene facts estructurales no presentes en canonical.
- Ejemplo conceptual: `la princesa` o `the princess` como title/role de `Sera`.
- Futuro botón UI: Attach role/title.

### `review_enrich_existing_entity`

- Cuándo: surface no es alias puro, pero trae facts útiles para enriquecer entidad existente.
- Para descriptor absorbido, emitir solo si trae evidencia no trivial: facts múltiples, evidencia multi-capítulo o confianza suficiente.
- Evidence esperado: facts nuevos, candidate entity, reason de enrichment.
- `candidate_entities`: candidato probable.
- Severity sugerida: `medium` o `high` si se perderían facts estructurales.
- Ejemplo conceptual: descriptor con más información que el nombre canonical.
- Futuro botón UI: Enrich existing entity.

## Signal Tiers

### `high`

Usar con cuidado. Aplica cuando una entidad durable o descriptor con evidencia alta tiene candidato fuerte, riesgo de contaminación canonical o facts estructurales que se perderían si se descartan.

### `medium`

Default para objeto persistente omitido, descriptor/title con candidato probable, role/title/descriptor que necesita revisión o missing persistent entity sin candidato claro.

### `low`

Para evidencia débil, mención recurrente no estructural o posible secondary mention.

### `suppressed`

Para pronombre sin evidencia, clearly ephemeral/noise mention, una mención local no durable o forbidden primary mention del fixture.

## Candidate Guess Policy

- Proponer candidatos solo con overlap conservador: alias, source mentions, chapter refs, kind compatible o nombre similar.
- Nunca ejecutar merge ni promotion desde esta política.
- Incluir `reason`, `score` y `confidence_bucket` si existe.
- Incluir `do_not_auto_merge: true` en señales de retención/identidad.
- Si no hay candidato claro, usar `candidate_entities: []` y `candidate_status: no_clear_existing_primary` o `insufficient_evidence`.
- Estados esperados: `strong_candidate`, `weak_candidate`, `no_clear_existing_primary`, `insufficient_evidence`.

## Language-Agnostic Policy

- Ejemplos como `la princesa`, `the princess`, `ella`, `she`, `Mara` o `brújula de plata` no son lógica universal.
- La decisión principal debe basarse en `surface_type`, `entity_kind`, evidence count, overlaps, confidence, review state y discard reason.
- Si existe detección específica por lengua, debe estar aislada, explícita y extensible.
- Fallback conservador: si no sabemos, no promover ni mergear automáticamente.
- Roles, títulos y descriptores deben preservarse como semántica revisable aunque varíen por lengua.
- Descriptores genéricos con una sola mención débil se suprimen aunque estén absorbidos como alias/source mention, para evitar ruido.

## Descriptor Genericity Policy

Regla base: descriptor absorbido no implica review automático. Debe existir valor semántico no trivial y evidencia estructural.

Señales mínimas para evaluar descriptor absorbido:

- `surface_type`, `semantic_value`, `language_hint`.
- `candidate_entities` + `candidate_status` + `score`.
- `key_facts`, `chapter_refs`, `source_mentions`, `relationships`.
- novedad semántica frente a facts ya presentes en canonical.

Comportamiento conservador:

- `generic_descriptor`, `appearance_descriptor`, `age_or_demographic_descriptor`, `unknown_descriptor`: suprimir por defecto.
- subir a review solo si existe evidencia fuerte (facts nuevos relevantes, impacto relacional/canónico, persistencia multicapítulo con soporte).

## Descriptor Taxonomy

- `title_descriptor`: normalmente `review_attach_role_or_title`.
- `role_descriptor`: normalmente `review_attach_role_or_title`.
- `status_descriptor`: `attach`/`enrich` si expresa cambio canónico de estado.
- `relationship_descriptor`: `review_enrich_existing_entity` si añade relación con impacto.
- `epithet_descriptor`: señal solo con evidencia fuerte.
- `generic_descriptor`: suprimir o low.
- `appearance_descriptor`: suprimir salvo impacto canónico.
- `age_or_demographic_descriptor`: suprimir salvo impacto canónico explícito.
- `unknown_descriptor`: fallback conservador suprimir/low.

## Noise Budget

Presupuesto inicial de ruido:

- máximo 1 señal descriptor de severidad `medium` por `(candidate canonical, descriptor category, recommended_action)` por run lógico.
- extras equivalentes: degradar a `low` o suprimir.
- no emitir si no hay novedad semántica.
- dedupe por `source_entity/target_text/suggested_action` y equivalencia de candidato/categoría.

Si runtime no mantiene estado global extendido, aplicar primero en heurística de emisión por item (K-a) y extender a budget run-level en K-b.

## Future Viewer Actions

- Merge.
- Mark as alias.
- Promote to primary.
- Attach role/title.
- Enrich existing entity.
- Keep secondary.
- Reject noise.

Esta fase no implementa write-back ni botones. Solo deja metadata compatible para esas acciones futuras.

Contrato viewer-facing complementario:

- `docs/operations/viewer-review-actions-contract.md`
