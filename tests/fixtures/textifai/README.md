# TextifAI Safe Fixtures

Estos fixtures existen para validar partes del flujo semántico de TextifAI sin depender de material real, privado o costoso de regenerar.

## Reglas

- Todo fixture aquí debe ser sintético.
- No debe contener material privado del usuario.
- No debe copiarse desde `runs/` reales ni `vault/` reales sin sanitización explícita y aprobación.
- No deben escribirse outputs de pruebas en `runs/` ni en `vault/`.
- No deben incluir artifacts generados del pipeline como `obsidian_import.json`, `review_queue.json`, `semantic_invariants_audit.json` o metadata de jobs.
- Los futuros baselines y snapshots semánticos deben actualizarse solo con aprobación explícita.

## Uso esperado

Estos fixtures están pensados para fases posteriores como:

- contract snapshot tests
- replay baseline harness
- medición de ruido de extracción
- pruebas de estabilidad de alias/canonicalización
- validación de señal de review queue

## Fixture actual

- `minimal_novel/`
  - novela mínima sintética
  - 3 capítulos cortos
  - entidades persistentes intencionales
  - alias sencillo
  - menciones episódicas no persistentes

## Seguridad

- No ejecutar ingestión real sobre estos fixtures en esta fase.
- No llamar proveedores usando estos fixtures en esta fase.
- No escribir outputs dentro del directorio del fixture.
