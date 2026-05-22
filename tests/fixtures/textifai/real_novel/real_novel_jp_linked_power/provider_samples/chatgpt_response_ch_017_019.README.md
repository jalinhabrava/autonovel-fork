# ChatGPT middleman response (optional)

Este flujo permite obtener segunda extracción usando mismo blind prompt packet, sin llamadas automáticas en tests.

1. Copiar contenido de `prompt_packets/extraction_prompt_packet_ch_017_019.md`.
2. Pegar contenido completo en ChatGPT.
3. Pedir respuesta JSON estricto.
4. Guardar respuesta en:
   `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/chatgpt_response_ch_017_019.json`
5. Si archivo no existe, tests pasan con rama opcional.
6. Si archivo existe, tests validan parse/safety/shape y lo comparan con checklist dual.

Notas:
- Este archivo no implica canon approval.
- No usar capítulos completos.
- No incluir secretos/API keys/URLs de provider.
