# TODO

## Contexto del fork

Este proyecto es un fork de AutoNovel.

Objetivo general:
- Transformar AutoNovel desde un pipeline batch autónomo orientado a generar novelas desde una seed en un sistema narrativo persistente, modular y conversacional.

Qué queremos conseguir:
- Soporte para providers online y locales.
- Desacoplar la lógica del pipeline de providers concretos y de una estructura rígida de archivos.
- Integración con un Obsidian Vault como fuente de verdad persistente del proyecto.
- Capacidad de partir no solo de una seed, sino también de una novela ya en curso.
- Extracción automática inicial de artefactos como voz, personajes, canon, outline, lore y relaciones a partir de capítulos existentes.
- Modo conversacional con comandos granulares para escribir, revisar, validar y registrar decisiones.
- Capacidad de leer y escribir notas Markdown reales dentro del vault.
- Pipeline editorial avanzado con funciones como reader panel, editor review, adversarial review y revision briefs.

Principios del fork:
- No romper compatibilidad innecesariamente con el pipeline original mientras se refactoriza.
- Mantener los providers online actuales mientras se añaden providers locales.
- Trabajar por fases e hitos, evitando refactors masivos descontrolados.
- Toda abstracción nueva debe facilitar extensibilidad futura.
- La persistencia del conocimiento narrativo es un objetivo central del sistema.

Visión del producto:
- No queremos solo un “AI writer” que genere texto, sino una infraestructura narrativa que combine generación, memoria persistente, extracción de canon, edición conversacional y revisión editorial asistida.

## Fase 1 — Capa de inferencia estable

### Refactors base
- [x] Extraer capa de providers de texto
- [x] Añadir registry/factory de providers
- [x] Añadir selección global o por tarea
- [x] Mantener Anthropic y OpenAI
- [x] Añadir soporte local para LM Studio y Ollama
- [x] Centralizar modelos, límites y timeouts en config
- [x] Añadir tests mínimos de providers

### Objetivo funcional
- [x] Poder cambiar de provider en el core sin tocar scripts del pipeline

## Fase 2 — Abstracción del almacenamiento del proyecto

### Hitos
- [x] ProjectStore estable para artefactos, capítulos y estado
- [x] Workspace adapter compatible con el layout clásico de AutoNovel
- [x] Separar lógica del pipeline y rutas hardcodeadas en el core
- [x] Desacoplar `state.json` y `results.tsv` detrás del store
- [ ] Añadir adapter real para Obsidian Vault

### Objetivo funcional
- [x] El pipeline core funciona sin depender directamente de nombres/rutas de archivos concretos
- [ ] Poder leer/escribir desde una estructura externa compatible con vault

## Siguientes bloques
- [ ] Extraer/migrar los scripts legacy restantes fuera del core
- [ ] Implementar VaultProjectAdapter real
- [ ] Soporte para iniciar desde novela existente y extraer artefactos iniciales

## Fase 3 — Vault System / Obsidian Integration

### Subfases
- [x] 3A. Definir esquema oficial del vault
- [x] 3A. Definir plantillas base y frontmatter mínimo
- [x] 3B. Implementar Vault Bootstrap Wizard
- [x] 3B. Implementar validación básica del vault
- [x] 3C. Implementar VaultAdapter de lectura
- [x] 3D. Implementar VaultAdapter de escritura básica
- [x] 3D. Exponer comandos `init-vault`, `validate-vault`, `write-note`, `update-note`, `export-context`
- [x] 3D. Integrar selección `workspace|vault` en `ProjectStore`
- [x] 3E. Añadir capa de ingestión para capítulos existentes
- [x] 3E. Enriquecer metadata de origen del manuscrito y contexto digerido
- [x] 3E. Exponer comandos `import-existing-chapters` e `ingest-context`
- [ ] 3E. Implementar bootstrap semántico real desde novela existente mediante CLI/flujo interactivo externo
- [ ] 3E. Automatizar digestión editorial hacia estados `proposed` / `pending_revision` / `validated`

### Criterio funcional actual
- [x] Se puede crear un vault funcional desde cero en una ruta dada
- [x] El core puede leer y escribir sobre él a través del store
- [x] La estructura queda preparada para ser poblada automáticamente más adelante desde una novela ya en curso
