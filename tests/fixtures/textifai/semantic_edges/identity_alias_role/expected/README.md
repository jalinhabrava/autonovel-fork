# Expected Artifacts — identity_alias_role

Artifacts manuales y sintéticos para fijar contrato semántico edge.

## Propósito

- validar alias vs canonical
- validar title/role/descriptor preservation
- validar suppression de pronombres
- validar enrichment review
- validar retención de objeto persistente
- validar suppression de mención efímera

## Reglas

- no son outputs generados
- no provienen de `runs/` ni `vault/`
- no hay `replay_input/` todavía
- sirven como especificación humana antes de futura fase replay
- language-agnostic: las strings del fixture no son lógica universal

## Replay drift observations

Desde `safepoint-033`, `replay_drift_expectations.json` registra observación real provider-free:

- `Sera Valen` y `Ren Tal` retenidos como primaries.
- `la princesa`, `la heredera silenciosa` y `el muchacho` quedan como aliases/source mentions sin review signal dedicado.
- `ella` no queda como primary.
- `guardia somnoliento` queda suprimido.
- `llave de cristal` queda retenida como review entity con review item genérico, no como `entity_retention_review` con metadata nueva.

Estos son drifts conocidos, no fixes runtime.

### Safepoint 034 update

`llave de cristal` ya no se registra como drift de metadata de retención: el output esperado actual debe incluir un `entity_retention_review` moderno con `signal_tier`, `candidate_status`, `semantic_value`, `future_viewer_actions` y `do_not_auto_merge`.

Los drifts de descriptor/title/role (`la princesa`, `la heredera silenciosa`, `el muchacho`) siguen diferidos.

### Safepoint 035 update

`la princesa` y `la heredera silenciosa` ya no se registran como drift abierto: el replay esperado actual debe incluir señales explícitas de revisión editorial (`review_attach_role_or_title` y `review_enrich_existing_entity`) con `do_not_auto_merge`.

`el muchacho` se mantiene como drift explícito de descriptor genérico absorbido sin señal fuerte (`generic_descriptor_absorbed_without_review_signal`) para evitar ruido.
