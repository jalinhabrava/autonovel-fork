# Reglas de Diagnóstico de Ingestión Semántica End-to-End

## 1. Propósito

Este documento define las reglas obligatorias para evaluar ejecuciones de **ingestión semántica end-to-end hasta VaERL** del pipeline de novelas.

No define una E2E real de producto. Una E2E real de producto incluye importar la novela, construir el vault/VaERL, usarlo desde un chat libre del usuario y evaluar utilidad real en consulta. Este playbook termina antes: valida si la ingestión semántica produjo artefactos confiables para que VaERL y el vault puedan operar.

El pipeline tiene **dos bucles de iteración independientes**:

1. **Calidad de extracción semántica**
2. **Calidad de compilación / interpretación hacia VaERL**

⚠️ Regla crítica:

> Estos dos bucles no deben mezclarse. Toda evaluación debe identificar claramente a cuál pertenece cada fallo.

---

## 2. Fronteras del Pipeline (Artefactos de Verdad)

Las evaluaciones deben analizar los siguientes artefactos en orden:

En el rail activo actual de TextifAI, estos artefactos se persisten bajo:

`<vault_root>/99_System/`

### `global_normalization`

`global_normalization.json`

Pregunta:

* ¿La identidad semántica ya está mal aquí?

---

### `chapter_extraction`

`chapter_outputs/*.json`

Pregunta:

* ¿Los capítulos aportan evidencia útil o ruido?
* ¿Los nombres, tipos y facts son coherentes?
* ¿`chapter_extraction_audit.json` marca todos los capítulos esperados como generados?

---

### `entity_resolution`

`resolved_entities.json`

Pregunta:

* ¿La resolución de entidades (cluster resolution) adjudica correctamente identidades?

---

### `entity_cleanup`

`cleaned_entities.json`

Pregunta:

* ¿El cleanup promueve, filtra y clasifica correctamente?

---

### `obsidian_import`

`obsidian_import.json` o VaERL final

Pregunta:

* ¿La representación final refleja correctamente las entidades anteriores?

---

## 3. Reglas de Asignación de Responsabilidad

Toda evaluación debe identificar el **primer punto donde aparece el error**.

### Regla principal

* Si el error aparece por primera vez en:

  * `global_normalization.json` o `chapter_outputs`
    → pertenece a **prompt / extracción**

* Si aparece por primera vez en:

  * `resolved_entities.json` o `cleaned_entities.json`
    → pertenece a **resolución de entidades / cleanup**

* Si aparece solo en:

  * `obsidian_import.json` o vault final
    → pertenece a **assembly / importador / VaERL**

⚠️ Regla obligatoria:

> Nunca proponer cambios sin identificar primero la frontera donde nace el fallo.

### Nota de implementación del rail activo

En el pipeline activo actual:

- `global_normalization.json` se persiste
- `chapter_outputs/*.json` se persiste
- `resolved_entities.json` se persiste
- `cleaned_entities.json` se persiste
- `obsidian_import.json` se persiste

Si algún run concreto no contiene una de estas fronteras, debe tratarse como un run incompleto o no canónico para diagnóstico de ingestión semántica.

---

## 4. Cuándo modificar el prompt (extracción)

Modificar prompts o schemas SOLO cuando falla la verdad semántica de origen.

Ejemplos:

* protagonistas desaparecen o se fragmentan
* entidades importantes no aparecen
* una entidad nombrada se degrada a descriptor
* tipos incorrectos desde origen (`character` → `concept`)
* aliases basura se promueven a canonical
* errores ya visibles en `global_normalization` o `chapter_outputs`

⚠️ Regla:

> El compilador NO puede reconstruir semántica que no fue correctamente extraída.

---

## 5. Cuándo modificar el interpretador / compilador

Modificar resolución, cleanup o importador cuando:

* el JSON fuente es razonable
* pero el resultado final es incorrecto

Ejemplos:

* malas promociones a primary
* pérdida de relaciones
* mal colapso de aliases
* entidades duplicadas tras resolución
* tagging incorrecto
* ruido en VaERL

---

## 6. Reglas de congelación del prompt

El prompt debe congelarse temporalmente cuando:

* `named_primary_rate` es alto y estable
* `descriptor_primary_rate` es bajo y estable
* protagonistas aparecen consistentemente
* tipos principales (`character`, `place`, `faction`, `concept`) son razonables
* los errores dominantes pasan a ser:

  * merges incorrectos
  * promotion thresholds
  * clasificación fina
  * tagging
  * visualización

### Regla clave

> Si el JSON fuente “huele bien” en inspección manual de 10–20 capítulos, dejar de iterar el prompt temporalmente.

---

## 7. Cuándo volver a tocar el prompt

Reabrir trabajo en prompt si:

* protagonistas desaparecen o se fragmentan
* canonical naming colapsa
* reaparecen descriptor primaries
* tipos semánticos vuelven a ser incorrectos
* la semántica falla antes de `resolved_entities`

---

## 8. Estrategia de datasets

Se deben mantener tres niveles de evaluación:

### Dataset 1 — gold_small

* ~10 capítulos
* revisados manualmente
* uso: iteración rápida de prompts y semántica

---

### Dataset 2 — medium_regression

* 20–30 capítulos
* uso:

  * validar generalización
  * detectar errores de continuidad

---

### Dataset 3 — full_frozen_run

* novela completa (~100 capítulos)
* uso:

  * validación final
  * distribución de entidades
  * coste y performance

---

## 9. Política de costes (uso de API)

### Cuándo NO usar API

No llamar a la API si solo se cambia:

* `entity_cluster_resolution`
* `entity_cleanup`
* `assembly`
* `json_import`
* scoring
* tagging
* visualización

→ usar artefactos congelados de `global_normalization.json` / `chapter_outputs/*.json`
  para volver a calcular `resolved_entities.json`, `cleaned_entities.json` y `obsidian_import.json`

---

### Cuándo SÍ usar API

Solo en estos casos:

1. Cambios en prompts o schemas
2. Cambios en campos generados por LLM:

   * `canonical_candidate`
   * `naming_quality`
   * `review_reason`
3. Validación de generalización

---

## 10. Estrategia de iteración

### Bucle de extracción

* usar `gold_small`
* iteración rápida
* mínimo coste API

---

### Bucle de compilación

* usar artefactos congelados
* cero o mínimo uso de API
* iterar resolución, cleanup, assembly

---

### Bucle de validación

* usar `medium_regression`
* ocasionalmente `full_frozen_run`

---

## 11. Regla de decisión global

> Un prompt es suficientemente robusto cuando los errores dominantes dejan de ser de extracción y pasan a ser de resolución o compilación.

---

## 12. Formato obligatorio de respuesta de Codex

Cuando se evalúe una ingestión semántica end-to-end hasta VaERL, la respuesta debe seguir EXACTAMENTE esta estructura:

### 1. Observed improvements

* lista concreta

### 2. Observed regressions

* lista concreta

### 3. First failing boundary

* `global_normalization` / `chapter_extraction` / `entity_resolution` / `entity_cleanup` / `obsidian_import`
* justificar

### 4. Likely owner

* prompt / extraction
* cluster resolution
* cleanup
* assembly / importer

### 5. Recommended next change

* cambio mínimo necesario
* no rediseños globales

### 6. Need API rerun?

* yes / no
* justificar

### 7. Confidence

* alta / media / baja

---

## 13. Disciplina de alcance

Codex debe:

* no proponer reescrituras completas del pipeline
* no mezclar extracción con compilación
* identificar SIEMPRE la primera frontera de fallo
* proponer el cambio más pequeño posible
* justificar cualquier cambio en función de estas reglas
* Solo puedes diagnosticar la primera frontera de fallo usando artefactos homólogos del mismo run actual.
* No puedes usar artefactos legacy, runs anteriores, JSONs viejos ni fichas manuales externas como sustituto implícito de fronteras del pipeline.
* Si faltan fronteras del run actual, debes decir explícitamente:
“No hay evidencia suficiente para asignar concluyentemente la primera frontera de fallo”.

---

## 14. Principio final

> Diagnosticar primero dónde nace el error.
> Solo después decidir qué cambiar.

Cualquier recomendación que no respete este orden se considera inválida.
