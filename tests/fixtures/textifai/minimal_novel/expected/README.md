# Expected Artifacts — minimal_novel

Estos artifacts son snapshots contractuales sintéticos, escritos manualmente.

Objetivo:

- fijar forma y campos críticos de artifacts semánticos
- detectar cambios accidentales de contratos en fases futuras
- evitar dependencia de ingestión real o provider calls

Reglas:

- no generar estos archivos desde `runs/` reales o `vault/` reales
- no incluir datos privados
- mantener tamaño pequeño y revisable
- actualizar solo con aprobación explícita

Artifacts incluidos:

- `obsidian_import.json`
- `review_queue.json`
- `semantic_invariants_audit.json`
