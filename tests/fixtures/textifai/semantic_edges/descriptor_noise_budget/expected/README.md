# Expected Artifacts — descriptor_noise_budget

Artifacts manuales y sintéticos para contrato de genericidad descriptor, ruido, review-state candidates y dedupe de señales equivalentes.

No son outputs generados por pipeline. Sirven como baseline humano para K-b1/K-b2/K-b3a/K-b3b/K-b3c.

## K-b2 / K-b3a / K-b3b

- K-b2 fijó contratos replay y drift explícito.
- K-b3a diagnosticó causa: `Ari Mar` quedaba en `review_entity` y las surfaces descriptor no llegaban a señales dedicadas.
- K-b3b habilitó signals sobre review-state candidates sin auto-merge ni auto-promote.

## K-b3c update

K-b3c reduce señales equivalentes para evitar cola repetitiva:

- conserva una señal principal `medium`;
- degrada equivalentes cercanas a `low`;
- mantiene señales distintas si facts o relationships difieren;
- no cambia schema;
- no implementa write-back.

Comportamiento esperado:

- `el cartógrafo sin memoria` -> `review_enrich_existing_entity` `medium`;
- `el capitán del paso` -> `review_attach_role_or_title` `medium`;
- `el guardián del archivo` / `el custodio del paso` -> `low` por equivalencia si no aportan decisión editorial distinta;
- `el protector de Luma` -> `review_enrich_existing_entity` relacional `medium`;
- pronoun/noise/generic weak siguen suprimidos.
