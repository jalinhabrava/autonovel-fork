# Expected Artifacts — descriptor_noise_budget

Artifacts manuales y sintéticos para contrato de genericidad descriptor, ruido y señales de revisión editorial.

No son outputs generados por pipeline. Sirven como baseline humano para K-b1/K-b2/K-b3a/K-b3b.

## K-b2 / K-b3a

- K-b2 fijó contratos replay y drift explícito.
- K-b3a diagnosticó causa: `Ari Mar` quedaba en `review_entity` y las surfaces descriptor no llegaban a señales dedicadas.

## K-b3b update

K-b3b no promueve canon automático. Habilita señales descriptor útiles sobre candidatos en review state:

- review-state candidate usable para signals editoriales;
- `do_not_auto_merge: true`;
- `do_not_auto_promote: true`;
- metadata moderna en items descriptor dedicados (`candidate_review_state`, `candidate_requires_review`, `descriptor_category`, `surface_type`, `semantic_value`).

Comportamiento esperado:

- `el cartógrafo sin memoria` -> `review_enrich_existing_entity`;
- `el capitán del paso` -> `review_attach_role_or_title`;
- `el protector de Luma` -> `review_enrich_existing_entity` compatible relacional;
- pronoun/noise/generic weak siguen suprimidos;
- schema sin cambios, write-back sin cambios.
