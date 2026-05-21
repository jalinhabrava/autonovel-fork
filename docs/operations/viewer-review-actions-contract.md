# Viewer Review Actions Contract

## Purpose

`review_queue.json` puede describir acciones editoriales sugeridas, pero el viewer solo las presenta como decisiones humanas pendientes. Esta capa es read-only: no ejecuta merge, promote, alias write-back ni mutación de artifacts.

## Inputs

Campos relevantes por item:

- `review_type`
- `severity`
- `source_entity`
- `target_text`
- `candidate_entities`
- `evidence`
- `metadata.recommended_action`
- `metadata.signal_tier`
- `metadata.candidate_status`
- `metadata.surface_type`
- `metadata.semantic_value`
- `metadata.language_hint`
- `metadata.future_viewer_actions`
- `metadata.do_not_auto_merge`

## Action Descriptors

### `merge`

- Cuándo aparece: `review_merge_or_alias` o `future_viewer_actions` explícito.
- Label sugerido: `Future action: Merge`
- Explicación: posible merge into canonical entity.
- Preconditions: `candidate_entities` disponible.
- Required fields: `candidate_entities`, `metadata.recommended_action`.
- Safety warnings: read-only; nunca auto-merge.
- Future write-back target: merge into canonical entity.

### `mark_alias`

- Cuándo aparece: `review_merge_or_alias` o lista explícita.
- Label sugerido: `Future action: Mark alias`
- Explicación: posible alias attachment a entidad existente.
- Preconditions: candidato disponible.
- Required fields: `candidate_entities`.
- Safety warnings: read-only.
- Future write-back target: add alias to entity.

### `promote`

- Cuándo aparece: `review_create_primary`.
- Label sugerido: `Future action: Promote`
- Explicación: posible promote to primary.
- Preconditions: señal durable y evidencia visible.
- Required fields: `metadata.recommended_action`, `metadata.semantic_value`.
- Safety warnings: read-only; no auto-promotion.
- Future write-back target: promote review entity.

### `attach_role_or_title`

- Cuándo aparece: `review_attach_role_or_title`.
- Label sugerido: `Future action: Attach role/title`
- Explicación: posible attach de role/title/descriptor a entidad existente.
- Preconditions: `surface_type` role/title/descriptor; candidato preferido si existe.
- Required fields: `metadata.surface_type`, `metadata.semantic_value`.
- Safety warnings: read-only; no attachment automático.
- Future write-back target: attach role/title/descriptor.

### `enrich_existing_entity`

- Cuándo aparece: `review_enrich_existing_entity`.
- Label sugerido: `Future action: Enrich existing entity`
- Explicación: posible enrich de canonical entity con facts retenidos.
- Preconditions: evidence y candidato.
- Required fields: `candidate_entities`, `evidence`.
- Safety warnings: read-only.
- Future write-back target: enrich existing entity.

### `keep_secondary`

- Cuándo aparece: `review_keep_secondary` o lista explícita.
- Label sugerido: `Future action: Keep secondary`
- Explicación: mantener como secondary mention.
- Preconditions: review item visible.
- Required fields: `review_type`.
- Safety warnings: read-only.
- Future write-back target: keep secondary mention.

### `reject_noise`

- Cuándo aparece: `review_reject_noise` o lista explícita.
- Label sugerido: `Future action: Reject noise`
- Explicación: marcar como ruido/noise.
- Preconditions: señal débil o noisy.
- Required fields: `review_type`.
- Safety warnings: read-only.
- Future write-back target: reject/noise suppression.

## Recommended Action Mapping

- `review_merge_or_alias` → `merge`, `mark_alias`
- `review_create_primary` → `promote`
- `review_keep_secondary` → `keep_secondary`
- `review_reject_noise` → `reject_noise`
- `review_insufficient_evidence` → none / inspect evidence only
- `review_attach_role_or_title` → `attach_role_or_title`
- `review_enrich_existing_entity` → `enrich_existing_entity`

Si `metadata.future_viewer_actions` existe, esa lista explícita tiene prioridad visual sobre el fallback de `recommended_action`.

## Safety Rules

- Do not execute automatically.
- Do not show destructive button as active.
- All actions are advisory/read-only for now.
- All action buttons should be disabled or labelled `future action`.
- Preserve evidence and rationale.
- Never hide `do_not_auto_merge`.
- If candidate is missing, show `no clear candidate`.
- If surface is pronoun-like, show conservative warning.

## Language-Agnostic Behavior

- UI labels pueden localizarse más tarde.
- Action logic no depende de strings españolas/inglesas.
- Viewer lee `surface_type`, `semantic_value`, `candidate_status`.
- Lenguas desconocidas usan wording conservador.

## Future Write-back Design

Futuros targets documentados, no implementados:

- merge into canonical entity
- add alias to entity
- attach role/title/descriptor
- promote review entity
- keep secondary
- reject/noise suppression
