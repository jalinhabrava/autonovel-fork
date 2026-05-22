# Blind prompt packets

Este directorio guarda packet(s) de prompt exportados para uso manual fuera del runtime.

- Objetivo: copiar/pegar packet en ChatGPT para extraer JSON narrativo.
- Modo: blind prompt (sin expected entities/lore/events/relationships).
- Tests: provider-free, sin llamadas de red/provider.
- Alcance de fuente: solo extractos breves ya versionados.
- Política: no capítulos completos, no novela completa.

Flujo:
1. Abrir `extraction_prompt_packet_ch_017_019.md`.
2. Copiar el contenido completo al chat manual de ChatGPT.
3. Pedir respuesta JSON estricto.
4. Guardar respuesta como `provider_samples/chatgpt_response_ch_017_019.json`.
5. Si archivo no existe, tests pasan igual.
