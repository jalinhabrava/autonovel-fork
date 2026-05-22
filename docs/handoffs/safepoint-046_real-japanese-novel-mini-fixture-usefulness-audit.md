# Real Japanese Novel Mini-Fixture Usefulness Audit

## Product Reading
Hasta ahora TextifAI se validó sobre fixtures sintéticos. Ya se cubrieron señales útiles, suppression de ruido, dedupe, anti-overfitting y viewer read-only. Esta fase introduce una prueba más realista con material real de la novela japonesa `王者の杖`, pero sin llamadas a provider: un `replay_input` manual tipo LLM sirve para auditar utilidad real downstream.

## Scope
- Crear mini-fixture realista separado en `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/`.
- Añadir extractos japoneses mínimos y seguros.
- Añadir `replay_input` manual provider-free.
- Añadir harness, baseline y usefulness contracts.
- Sin runtime changes, schema changes, provider calls ni write-back.

## Files Changed
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/source/README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/source/ch_017_excerpt.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/source/ch_018_excerpt.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/source/ch_019_excerpt.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/fixture_manifest.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/usefulness_checklist.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/replay_drift_expectations.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/replay_input/README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/replay_input/global_normalization.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/replay_input/chapter_outputs/ch_017.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/replay_input/chapter_outputs/ch_018.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/replay_input/chapter_outputs/ch_019.json`
- `tests/test_textifai_real_novel_jp_mini_fixture_harness.py`
- `tests/test_textifai_real_novel_jp_mini_replay_baseline.py`
- `tests/test_textifai_real_novel_jp_mini_usefulness_contracts.py`
- `docs/handoffs/safepoint-046_real-japanese-novel-mini-fixture-usefulness-audit.md`

## Fixture Created
Se creó `real_novel_jp_linked_power`, mini-fixture realista para capítulos 17–19 de `王者の杖`.

## Source Excerpt Policy
- Solo extractos breves y representativos.
- No capítulos completos.
- `source/` sirve para trazabilidad mínima.
- La fuente principal de tests es `replay_input/` estructurado.

## LLM-like Extraction Seed
El fixture implementa una semilla LLM-like/manual para:
- レン
- セラ
- ベルド / オヤジ
- ガントレットの男
- ベル
- ガントレット
- エルサリエル
- 王者と杖
- 繋がった力
- pronouns controlados (`彼`, `彼女`, `俺`, `私`)

## Replay Input Created
Se añadieron:
- `global_normalization.json`
- `ch_017.json`
- `ch_018.json`
- `ch_019.json`

Con observations de misión, activación deベル, magia enlazada, muerte deベルド y aftermath entreレン/セラ.

## Usefulness Checklist
Checklist distingue:
- `must_have`
- `should_have`
- `accepted_temporary_drift`
- `non_negotiable_failures`

Foco: utilidad narrativa real, no perfección exhaustiva.

## Useful Entities / Relations / Events
Validado provider-free:
- レン y セラ aparecen.
- ベルド / オヤジ aparece como entidad revisable/útil.
- ベル aparece como objeto duradero.
- エルサリエル aparece como destino/lugar.
- `王者と杖` sobrevive como lore/review concept.
- `繋がった力` sobrevive como lore/relación/facts.
- muerte/aftermath deベルド sobreviven como facts útiles.

## Suppression / Noise Expectations
- `彼`, `彼女`, `俺`, `私` no deben promocionarse como primaries fuertes.
- `ベル` no debe degradarse a ruido.
- props efímeros no deben dominar output.

## Replay Baseline
Replay downstream provider-free corre en `TemporaryDirectory`, escribe solo dentro de temp output y no toca `runs/**` ni `vault/**`.

## Usefulness Contracts
Los contratos verifican utilidad amplia y segura:
- entidades/candidatos esenciales
- facts/relations/lore relevantes
- suppression de pronombres
- review queue con valor narrativo o canon suficiente
- no auto-merge / no auto-promotion / no write-back

## Provider-free Guarantee
Tests parchan `get_text_provider` para fallar si hay llamada. Además se desactiva el validador de prosa estricta para `ja` con modo `warn` y `prose_language_validator=None`.

## IP / Privacy Constraints
- Sin novela completa.
- Sin dumps de capítulos completos.
- Extractos mínimos y cortos.
- Fixture documenta limitación de IP/privacidad.

## Tests Added / Updated
Añadidos:
- `tests/test_textifai_real_novel_jp_mini_fixture_harness.py`
- `tests/test_textifai_real_novel_jp_mini_replay_baseline.py`
- `tests/test_textifai_real_novel_jp_mini_usefulness_contracts.py`

## Validation Performed
Ejecutado OK:
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_usefulness_contracts`
- `uv run python -m unittest -v tests.test_textifai_review_state_candidate_noise_budget_dedupe`
- `uv run python -m unittest -v tests.test_textifai_descriptor_noise_budget_variant_replay_contracts`
- `uv run python -m unittest -v tests.test_textifai_web_viewer`
- `node --check textifai/web_viewer/static/app.js`
- `uv run python scripts/textifai.py replay-downstream --help`
- `uv run python scripts/textifai.py viewer --help`
- `git status --short`
- `git diff --stat`

## Data Written
- Fixture manual y extractos mínimos en `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/**`
- Output de replay solo en tempdirs de tests

## Safety Constraints
- Sin runtime changes.
- Sin schema changes.
- Sin provider calls.
- Sin write-back.
- Sin escritura en `runs/**` o `vault/**`.

## Known Limitations
- Fixture representa solo 3 capítulos y extractos mínimos.
- Eventos pueden quedar como facts, no como entidades/eventos first-class.
- Alias ベルド/オヤジ puede seguir necesitando revisión humana.

## Future Extensions
- Comparar extracción real con provider frente a este replay_input curado.
- Extender fixture con más capítulos o otros arcos si política IP lo permite.
- Auditar viewer con output real-novel más denso.

## Semantic Contract Changes
NO

## Runtime Changes
NO

## Generated Artifacts
Manual fixture/replay input only; temp-only replay output.

## Provider Calls
NO

## Write-back
NO

## Branch
`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase
Phase 1.3.M-b — Real Japanese Novel Provider Extraction Comparison Audit.
