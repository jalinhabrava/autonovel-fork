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
