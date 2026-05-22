# Expected Artifacts — descriptor_noise_budget

Artifacts manuales y sintéticos para especificar contrato deseado de genericidad de descriptores y presupuesto de ruido.

No son outputs generados por pipeline. Sirven como baseline humano para K-b1/K-b2/K-b3a.

## K-b2 update

K-b2 observa replay output real provider-free y separa en `replay_drift_expectations.json`:

- expectativa manual;
- comportamiento observado actual;
- drift temporal aceptado;
- comportamiento resuelto actual;
- fallos no negociables;
- futuro deseado.

Esta fase no implementa budget run-level real, no cambia schema y no introduce write-back. Si el output actual no emite signals de descriptor esperados, el drift queda explícito en vez de ocultarse.

## K-b3a update

K-b3a no corrige runtime. Hace diagnóstico explícito de causa probable:

- `Ari Mar` absorbe surfaces descriptor, pero queda como `review_entity` genérico;
- no hay primaries top-level en output final;
- las surfaces esperadas sobreviven como aliases/source mentions;
- no reaparecen como signals descriptor dedicados en `review_queue.json`.

Por eso esta fase deja medible si bloqueo viene de estado de candidato, retención de metadata de surface o path conservador de signalización.
