# Real bootstrap prompt capture provider samples

Este fixture guarda respuestas manuales de ChatGPT obtenidas a partir de prompts reales capturados por `scripts/dev/capture_bootstrap_prompts.py`.

## Sample actual

- `chatgpt_response_bootstrap_chapter_extraction_ja_ch_001.json`
- task capturada: `bootstrap_chapter_extraction`
- source privada usada por el usuario: `/home/david/OnT/王者の杖.md`
- chapter capturado: `ch_001`
- title: `**（仮）証人**`
- language: `ja`
- canonical map en prompt: vacío (`CANONICAL_ENTITY_MAP: []`)

## Política

- No contiene prompt capturado completo.
- No contiene capítulo completo fuente.
- Contiene solo respuesta JSON manual de ChatGPT aprobada como sample de auditoría.
- No es canon approval.
- No es provider runtime output.
- Tests son provider-free y solo leen archivos versionados.
