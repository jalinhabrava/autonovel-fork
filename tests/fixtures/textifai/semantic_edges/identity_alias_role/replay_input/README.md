# Replay Input Fixture — identity_alias_role

Input manual, sintético y versionado para `replay-downstream` sobre el fixture edge `identity_alias_role`.

## Propósito

- observar replay provider-free en casos edge de identidad, alias, roles y retención
- usar artifacts congelados pequeños y revisables
- evitar ingestión real, provider calls y writes fuera de `TemporaryDirectory`

## Incluye

- `global_normalization.json`
- `chapter_outputs/ch_001.json`
- `chapter_outputs/ch_002.json`
- `chapter_outputs/ch_003.json`

## Reglas

- no proviene de `runs/` ni de `vault/`
- no usar material privado
- no escribir outputs dentro de este directorio
- no comprometer outputs generados fuera de `replay_input/`
- las strings del fixture no son lógica universal; la evaluación posterior debe apoyarse en metadata estructural
