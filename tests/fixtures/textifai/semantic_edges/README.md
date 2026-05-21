# TextifAI Semantic Edge Fixtures

Estos fixtures cubren casos sintéticos edge para identidad, alias, roles, títulos, descriptores, pronombres y retención.

## Reglas

- Todo fixture aquí debe ser sintético y pequeño.
- No debe contener material privado ni texto real del usuario.
- Los artifacts en `expected/` son manuales; no son outputs generados.
- No debe existir `replay_input/` hasta una fase futura explícita.
- No deben escribirse outputs en `runs/` ni en `vault/`.

## Fixture actual

- `identity_alias_role/`
  - 3 capítulos cortos en español
  - alias claros y superficies narrativas ambiguas
  - caso de pronombre suppressed
  - caso de título/rol revisable
  - caso de descriptor con facts para enrichment review
  - caso de objeto persistente durable
  - caso de mención efímera/noise

## Política

- Las strings del fixture no son lógica universal.
- Las decisiones esperadas deben apoyarse en metadata estructural como `surface_type`, `semantic_value`, `candidate_status`, `language_hint`, `recommended_action` y `future_viewer_actions`.
