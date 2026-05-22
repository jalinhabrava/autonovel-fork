# Provider samples (manual comparison)

Este directorio guarda **samples manuales estilo provider** para auditoría comparativa.

- `sample_type`: manual_chatgpt_style_provider_sample
- `provider_calls`: false
- `for_tests`: true
- `not_canon_approval`: true

No son canon aprobado. No son salida automática del runtime. Se usan para comparar prompt/schema vs replay curado.

## Blind prompt packet audit

- `prompt_packets/extraction_prompt_packet_ch_017_019.md`: packet RAW copiable para ChatGPT.
- `prompt_packets/extraction_prompt_packet_ch_017_019.json`: packet estructurado con flags provider-free.
- `codex_blind_simulated_extraction_ch_017_019.json`: extracción simulada por Codex desde packet blind.
- `chatgpt_response_ch_017_019.README.md`: flujo manual para añadir respuesta ChatGPT futura.

El packet blind no contiene expected entities/lore/events/relationships. Las comparaciones viven en `expected/`.
