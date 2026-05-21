# Replay Input Fixture — minimal_novel

Este directorio contiene input sintético manual para `replay-downstream`.

Propósito:

- validar replay downstream en entorno seguro
- usar artifacts congelados pequeños y versionados
- evitar ingestión real y provider calls

Incluye:

- `global_normalization.json`
- `chapter_outputs/ch_001.json`
- `chapter_outputs/ch_002.json`
- `chapter_outputs/ch_003.json`

Reglas:

- no copiar desde `runs/` reales ni `vault/` reales
- no usar material privado
- no escribir outputs dentro de este directorio
- outputs de smoke test deben ir a `tempfile.TemporaryDirectory`
