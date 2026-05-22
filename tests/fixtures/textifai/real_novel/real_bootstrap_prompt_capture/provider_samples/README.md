# Real bootstrap prompt capture provider samples

Este fixture guarda respuestas manuales de ChatGPT obtenidas a partir de prompts reales capturados por `scripts/dev/capture_bootstrap_prompts.py`.

## Samples actuales

- `chatgpt_response_bootstrap_chapter_extraction_ja_ch_001.json`
  - baseline `safepoint-050`
  - task capturada: `bootstrap_chapter_extraction`
  - source privada usada por el usuario: `/home/david/OnT/王者の杖.md`
  - chapter capturado: `ch_001`
  - title: `**（仮）証人**`
  - language: `ja`
  - canonical map en prompt: vacío (`CANONICAL_ENTITY_MAP: []`)

- `chatgpt_response_bootstrap_chapter_extraction_ja_ch_001_after_sp051.json`
  - hardened comparison sample para `safepoint-052`
  - prompt real usado: captura post-`safepoint-051`
  - task capturada: `bootstrap_chapter_extraction`
  - source privada usada por el usuario: `/home/david/OnT/王者の杖.md`
  - chapter capturado: `ch_001`
  - title: `**（仮）証人**`
  - language: `ja`
  - canonical map en prompt: vacío (`CANONICAL_ENTITY_MAP: []`)
  - prompt endurecido contiene `chapter_extraction_schema_version: v2`, `objects`, `CANONICAL_MAP_MODE`, `relation_category`, `relation_label`, `event_importance`

- `chatgpt_response_bootstrap_global_normalization_ja_batch_001_after_sp051.json`
  - manual global normalization sample para `safepoint-053`
  - prompt real usado: captura post-`safepoint-051`
  - task capturada: `bootstrap_global_normalization`
  - source privada usada por el usuario: `/home/david/OnT/王者の杖.md`
  - batch scope: `ch_001`, `ch_002`, `ch_003`
  - language: `ja`
  - provider-free manual ChatGPT sample
  - no es provider runtime output
  - no es canon approval

## Política

- No contiene prompt capturado completo.
- No contiene capítulo completo fuente.
- Contiene solo respuestas JSON manuales de ChatGPT aprobadas como samples de auditoría.
- No es canon approval.
- No es provider runtime output.
- Tests son provider-free y solo leen archivos versionados.
