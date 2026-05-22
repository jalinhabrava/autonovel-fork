# Blind Prompt Packet Export & Dual LLM Extraction Audit

## Product Reading

`safepoint-047` creó prompt/schema v1 y sample manual estilo provider. Eso no prueba todavía que prompt real produzca buena extracción sin pistas. Esta fase exporta packet RAW blind, genera simulación Codex desde ese packet, y deja flujo ChatGPT manual para comparar después contra replay curado sin contaminar input LLM.

## Scope

- Crear prompt packet RAW copiable.
- Crear packet JSON estructurado.
- Crear extracción Codex blind simulada.
- Crear checklist dual y audit report.
- Añadir tests provider-free.
- No tocar runtime, viewer, provider, ingestion ni chunking.

## Files Changed

- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/prompt_packets/README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/prompt_packets/extraction_prompt_packet_ch_017_019.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/prompt_packets/extraction_prompt_packet_ch_017_019.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/codex_blind_simulated_extraction_ch_017_019.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/chatgpt_response_ch_017_019.README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/provider_samples/README.md`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/provider_dual_comparison_checklist.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/prompt_packet_audit_report.json`
- `tests/fixtures/textifai/real_novel/real_novel_jp_linked_power/expected/README.md`
- `tests/test_textifai_real_novel_jp_prompt_packet_export.py`
- `tests/test_textifai_real_novel_jp_dual_llm_extraction_audit.py`
- `docs/handoffs/safepoint-048_blind-prompt-packet-export-dual-llm-extraction-audit.md`

## Blind Prompt Packet Exported

Packet RAW exportado en Markdown y JSON. Contiene instrucciones generales, schema y source payload mínimo para `ch_017`, `ch_018`, `ch_019`.

## Prompt Packet Contents

- Purpose general de extractor narrativo TextifAI.
- Rules generales de no invención, surfaces originales, incertidumbre, no auto-merge, no auto-promote.
- Schema con top-level keys obligatorias.
- Source chunk payload excerpt-only.
- Final instruction JSON-only.

## Anti-Leakage Policy

El packet blind no contiene expected entities, expected objects, expected lore, expected events, expected relationships, curated replay facts ni checklist. Tests revisan frases prohibidas fuera del source payload.

## Codex Blind Simulated Extraction

`codex_blind_simulated_extraction_ch_017_019.json` simula salida Codex usando solo packet blind. Marcada como `provider_calls: false`, `not_runtime_provider_output: true`, `not_canon_approval: true`, `blind_prompt: true`.

## ChatGPT Middleman Flow

`chatgpt_response_ch_017_019.README.md` explica cómo copiar packet Markdown a ChatGPT y guardar respuesta opcional como JSON. Tests no fallan si respuesta ChatGPT aún no existe.

## Dual Comparison Checklist

`provider_dual_comparison_checklist.json` define comparación post-output entre replay curado, Codex blind y ChatGPT opcional.

## Prompt Packet Audit Report

`prompt_packet_audit_report.json` marca packet como `ready_for_manual_chatgpt_trial`, anti-leakage `passed_no_expected_leakage`, ChatGPT `not_provided_yet`, readiness `prompt_needs_minor_revision`.

## PASS / FAIL States

- `prompt_promising`
- `prompt_needs_minor_revision`
- `prompt_needs_major_revision`
- `prompt_not_usable`

## What Blind Codex Simulation Covered

- Entidades principales (`レン`, `セラ`, `オヤジ`/`ベルド` como uncertainty).
- Objeto clave `ベル`.
- Lugar `エルサリエル`.
- Lore `王者と杖` y `繋がった力`.
- Eventos: activación del bell, magia conjunta, muerte/pérdida de ベルド,名乗り.
- Suppression de pronombres.

## What Was Missing / Weaker

- Alias `オヤジ` ↔ `ベルド` sigue medio/uncertain.
- Estructura de eventos menos rica que replay curado.
- Role mapping `王者`/`杖` sigue necesitando revisión autoral.

## What Remains Unproven

- ChatGPT real todavía no produjo sample.
- Provider API real no probado.
- Prompt integrado en ingestion no probado.
- Chunking/token budget no auditado.

## Provider-free Guarantee

Tests solo leen archivos JSON/Markdown. No hay imports provider, secrets, red ni API.

## IP / Privacy Constraints

Solo extractos breves ya versionados. No capítulos completos, no novela completa.

## Tests Added / Updated

- `tests/test_textifai_real_novel_jp_prompt_packet_export.py`
- `tests/test_textifai_real_novel_jp_dual_llm_extraction_audit.py`
- README provider/expected actualizados.

## Validation Performed

- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_prompt_packet_export`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_dual_llm_extraction_audit`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_provider_sample_contracts`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_provider_comparison_audit`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_fixture_harness`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_replay_baseline`
- `uv run python -m unittest -v tests.test_textifai_real_novel_jp_mini_usefulness_contracts`

## Data Written

Fixture docs/tests only. No `runs/**`. No `vault/**`.

## Safety Constraints

- No provider calls.
- No runtime changes.
- No schema runtime changes.
- No write-back.
- No chunking changes.
- No full chapter dumps.

## Known Limitations

Codex self-simulation is not same as real ChatGPT/API behavior. It can only indicate prompt plausibility.

## Future Extensions

Add optional ChatGPT response JSON and compare against dual checklist. Later run real provider experiment outside unittest if approved.

## Next Chunking Audit

Next phase should audit chapter/title splitting, messy author notes, worldbuilding, magic-system notes, token budget, overlap policy, context preservation, anti-overlong chunks, and per-chunk metadata.

## Semantic Contract Changes

None.

## Runtime Changes

None.

## Generated Artifacts

Manual fixture artifacts only: blind prompt packet, Codex blind sample, checklists, audit report.

## Provider Calls

None.

## Write-back

None.

## Branch

`phase-1.3-ingestion-vaerl-hardening`

## Next Suggested Phase

Phase 1.3.M-b3 — ChatGPT Middleman Response Comparison, or Phase 1.3.N — Chunking & Token Budget Audit.
