# Patch VaERL Projection + Retry/Review Mapping

## Product Reading
TextifAI es motor de ingestión VaERL, gestor/visor de VaERL y base para editor interactivo AI-powered. El viewer no puede ser debug-only: debe funcionar como gestor narrativo author-facing inspirado en Obsidian/KB. SP-088 mostró que extracción privada sí tenía labels reales, pero la proyección SP-087 los degradó a labels sintéticas y clasificó low-density como retry técnico. Este safepoint corrige proyección y mapping sin providers, retry real, full-source ni write-back.

## Scope
- Patch provider-free de proyección VaERL/viewer graph.
- Patch de overview, node detail data y artifacts debug role.
- Patch de clasificación retry/review.
- Revalidación sintética y privada privacy-safe.

## Files Changed
- `textifai/import_review/viewer_graph_adapter.py`
- `textifai/import_review/chunking_reduction_preflight.py`
- `textifai/web_viewer/project_reader.py`
- `textifai/web_viewer/static/app.js`
- `tests/test_textifai_vaerl_projection_patch.py`
- `tests/fixtures/textifai/viewer_patch/expected/*.json`
- `tests/fixtures/textifai/retry_patch/expected/*.json`
- `docs/handoffs/safepoint-089_vaerl-projection-retry-review-mapping-patch.md`

## SP088 Context
SP-088 auditó que runtime graph privado de SP-087 contenía 100/100 labels sintéticas, aunque reductions privadas tenían labels no sintéticas en 20/20 capítulos. También estimó true technical retry en 0 y señaló que low score / low objects / low relations no deben mapear automáticamente a retry.

## Lean / Legacy Cleanup Decisions
- Ruta principal: core VaERL projection -> viewer graph.
- Se reutiliza filosofía Obsidian: labels canónicos, aliases, facts, note_path, tags, backlinks, relationships.
- Se depreca silent synthetic numbering para runtime real.
- Artifacts queda como debug/dev secundario, no experiencia principal.
- No se añadió fallback legacy amplio ni ruta paralela ambigua.

## Runtime Real Labels Policy
Runtime real usa `canonical_label`, `canonical_name`, `canonical`, `surface`, `name` o `title`. Si no hay ningún label real, se emite `label_missing_runtime_warning`. Labels tipo `Character 001`, `Object 012`, `Event 009` quedan permitidas solo en fixtures/tests commiteables, no como salida real silenciosa.

## VaERL Runtime Graph Projection
`viewer_graph_adapter.py` ahora preserva labels reales, aliases, surface forms, facts, summaries, chapter ids, source refs, evidence refs, note_path, tags, status y review state. Añade `build_runtime_ingestion_graph()` para construir graph provider-free desde payloads de capítulo.

## Obsidian-compatible Projection
La proyección conserva shape útil para Obsidian-like viewer: canonical labels, aliases, facts, relationships, note_path, tags, backlinks y markdown link cuando exista. No intenta mantener formato viejo si contradice contrato VaERL.

## Viewer Overview Patch
`project_reader.py` expone `overview` desde `ingestion_graph.metadata.writer_outcome` y `graph_summary`. `app.js` muestra capítulos procesados, ready, ready_with_warnings, review, retry, failed, relationships, node counts, warnings y CTA.

## Node Detail Data Contract
El detail panel puede mostrar label real, kind, aliases, surface forms, summary, facts, source refs, evidence refs, incoming/outgoing relationships, status, note_path, tags y backlinks. No hubo rediseño visual completo.

## Relationship Projection Patch
Relations usan `from_canonical/from_surface`, `to_canonical/to_surface`, `relation_label`, `relation_category`, facts, source refs y evidence refs. `appears_in/happens_at` ya no reemplaza relación semántica cuando existe label real.

## Artifacts / Debug Role
Artifacts se etiqueta como `Debug / Artifacts` y queda como vista técnica secundaria. Author flow principal: Overview + Graph + node detail.

## Retry / Review Mapping Patch
`map_technical_signals_to_writer_status()` reserva `needs_retry` para fallos técnicos/incompletos. Low-density, thin, low objects, low relations o low score con output válido pasan a `needs_review` o `ready_with_warnings`.

## SP087 Reclassified Writer Outcome
Reclasificación provider-free: previous 6 ready, 13 needs_retry, 1 needs_review. Nuevo resultado conceptual: 6 ready, 14 needs_review, 0 needs_retry. Confianza medium-high porque 20/20 reductions fueron válidas y parseables.

## Fail-only Rerun Plan Patch
Fail-only rerun ahora excluye capítulos review-only. Expected calls para SP-087 reclasificado: 0. Sugerencia: revisión humana antes de cualquier rerun.

## Writer Outcome Mapping Patch
Si no hay retries, CTA principal pasa a `Review results`. Si hay reviews, el mensaje muestra cuántos capítulos necesitan revisión. Si hay retries técnicos reales, muestra cuántos necesitan volver a procesarse. Writer-facing text no expone términos internos.

## Revalidation
- Fixture sintética valida labels tipo Ada/Farmhouse/Copper Key y relación `finds`.
- Private SP-087 reprojected provider-free en `/tmp`.
- Before synthetic labels: 100.
- After synthetic labels: 0.
- Reprojected graph: 430 nodes, 91 edges.
- Labels reales no listados en repo.

## Viewer Manual Review Server
No se reinició server para no interrumpir browser manual ya abierto en `http://localhost:8870/`. Endpoints actuales respondieron 200 para `/` y `/api/projects`. Comando disponible para proyecto reprojected:
`/home/david/.local/bin/uv run python -m textifai.web_viewer.server --root /tmp/textifai_private_provider_runs/sp087_twenty_chapter_e2e_viewer/20260526T100011Z/20260526T100049Z --host 0.0.0.0 --port 8870`

## General Pipeline Learnings
- Privacy-safe commit no debe degradar runtime app output.
- Core VaERL debe preservar labels reales, aliases, facts, evidence and relationships.
- Writer outcome debe separar estado técnico de riqueza semántica.
- Viewer MVP puede mejorar incrementalmente sin rediseño completo.

## Provider-specific Learnings
- Viewer no depende de DeepSeek.
- DeepSeek puede afectar densidad, pero retry/review mapping debe ser provider-agnostic salvo fallos técnicos concretos.

## Product Decision
`vaerl_projection_retry_mapping_patch_ready_for_viewer_revalidation`

## Recommended Next Phase
Phase 1.3.M-b5c-4s — Manual Viewer Revalidation with Patched VaERL Projection

## What Worked
- Adapter preserva labels reales y datos narrativos.
- Retry mapping deja de convertir low-density válido en retry.
- Overview usa writer outcome real.
- Private SP-087 reprojected sin provider calls.

## What Failed
- No se reinició viewer server con proyecto SP-089 para evitar interrumpir sesión actual.
- Edge warnings siguen existiendo para nodos creados desde relations sin refs propios.
- Markdown materialization VaERL queda pendiente.

## Data Written
- Reports privacy-safe en `tests/fixtures/textifai/viewer_patch/expected/`.
- Reports privacy-safe en `tests/fixtures/textifai/retry_patch/expected/`.
- Private graph reprojected en `/tmp/.../viewer_project_sp089/99_System/ingestion_graph.json`.

## Privacy / Non-committed Output
No se commiteó `/tmp`, prompts privados, provider outputs privados, source prose ni source novel. Reports commiteados contienen métricas, decisiones y rutas.

## Tests Added / Updated
- Añadido `tests/test_textifai_vaerl_projection_patch.py`.
- Tests cubren labels reales, aliases/facts/source_refs, relaciones semánticas, overview, retry/review mapping, reports y writer terms.

## Validation Performed
- `uv run python -m unittest -v tests.test_textifai_vaerl_projection_patch`
- `uv run python -m unittest -v tests.test_textifai_vaerl_viewer_retry_audit`
- `uv run python -m unittest -v tests.test_textifai_viewer_preflight`
- `uv run python -m unittest -v tests.test_textifai_chunking_reduction_preflight`
- `uv run python -m unittest -v tests.test_textifai_prompt_experiment_observability`
- `uv run python -m unittest -v tests.test_textifai_deepseek_family_profiles`
- `uv run python -m unittest -v tests.test_textifai_provider_prompt_profiles`
- `uv run python -m unittest -v tests.test_textifai_real_provider_dryrun_guards`
- `uv run python -m unittest -v tests.test_text_provider`
- `DEEPSEEK_API_KEY='' uv run python -m unittest -v tests.test_textifai_provider_onboarding`
- Viewer root and projects endpoint returned 200.

## Safety Constraints
No provider calls. No OpenAI. No DeepSeek calls. No retry execution. No full-source. No write-back. No screenshots. No browser automation. No commit de `/tmp`.

## Known Limitations
- Viewer visual layout remains MVP.
- Relationship density still depends on extraction quality.
- Some nodes created only from relations may have missing source refs warnings.
- Full Obsidian markdown materialization remains future work.

## Future Extensions
- Manual viewer revalidation with patched private graph.
- VaERL note materialization with markdown/tags/backlinks.
- Calibrated density thresholds by chapter type.
- Author-facing review queue for valid-but-thin chapters.

## Runtime Changes
Runtime projection and viewer read/display contract changed. No irreversible data write-back.

## Write-back
NO.

## Branch
`phase-1.3-ingestion-vaerl-hardening`
