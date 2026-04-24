# AGENTS

This file contains essential instructions for working effectively with the TextifAI repository.

---

## Setup

- Copy `.env.example` to `.env` and fill in the provider keys required for the task.
  - `ANTHROPIC_API_KEY` is used by legacy/default Anthropic flows.
  - `OPENAI_API_KEY` is used by the current OpenAI-backed semantic ingestion runs when `AUTONOVEL_BOOTSTRAP_PROVIDER=openai`.
  - `FAL_KEY` and `ELEVENLABS_API_KEY` are optional for art and audiobook features.
- Use `uv run python <script.py>` to execute Python scripts (not plain `python`).
- This repository contains two rails:
  - Active TextifAI rail: `scripts/textifai.py` or `scripts/textifai_obsidian.py`, which delegate to `textifai.obsidian.cli` and `textifai.obsidian.setup.prepare_obsidian_project`.
  - Legacy AutoNovel rail: `run_pipeline.py` and `scripts/pipeline/run_pipeline.py` for the old foundation/drafting/revision/export flow.
- For narrative bootstrap / vault ingestion today, do not treat `run_pipeline.py` as the main orchestrator.

## Main Commands

### Active TextifAI bootstrap / ingestion

  ```
  uv run python scripts/textifai.py start
  uv run python scripts/textifai.py init --vault-root <vault> --source-root <source>
  uv run python scripts/textifai_obsidian.py inspect --vault-root <vault>
  ```

### Legacy AutoNovel pipeline

- Full pipeline (from scratch):
  ```
  uv run python run_pipeline.py --from-scratch
  ```

- Run individual pipeline phases:
  ```
  uv run python run_pipeline.py --phase foundation
  uv run python run_pipeline.py --phase drafting
  uv run python run_pipeline.py --phase revision
  uv run python run_pipeline.py --phase export
  ```

- Generate novel seed concepts:
  ```
  uv run python seed.py
  uv run python seed.py --count=5
  uv run python seed.py --riff "your idea"
  ```

## Evaluation and Revision

- Run evaluation and revision tools separately as needed:
  - `uv run python evaluate.py --phase=foundation`
  - `uv run python evaluate.py --chapter=5`
  - `uv run python evaluate.py --full`
  - `uv run python adversarial_edit.py all`
  - `uv run python apply_cuts.py all --types OVER-EXPLAIN REDUNDANT`
  - `uv run python reader_panel.py`
  - `uv run python review.py`
  - `uv run python gen_brief.py --auto`
  - `uv run python gen_revision.py [chapter] [brief_file]`

## Art and Audiobook

- Art requires `FAL_KEY` and uses `gen_art.py` and cover scripts.
- Audiobook requires `ELEVENLABS_API_KEY` and uses `gen_audiobook_script.py` and `gen_audiobook.py`.

## Architecture Notes

- Active TextifAI bootstrap pipeline:
  - source inventory / extraction: `textifai/bootstrap/source_reader.py`
  - chapter detection: `textifai/import_review/chapterizer.py`
  - structured bootstrap orchestration: `textifai/import_review/structured_bootstrap_v1.py`
  - vault setup / import: `textifai/obsidian/setup.py`, `textifai/obsidian/json_import.py`
- Legacy AutoNovel pipeline:
  - `scripts/pipeline/run_pipeline.py`
  - `scripts/foundation/`, `scripts/drafting/`, `scripts/revision/`
- The repo separates reusable framework files (master branch) and per-novel templates (feature branches).
- The novel exists as layered files:
  - `voice.md` for writing style
  - `world.md` for world bible
  - `characters.md` for character registry
  - `outline.md` for chapter outlines
  - `chapters/ch_NN.md` for actual prose
  - `canon.md` tracks lore truth constraints across layers
- Changes in one layer propagate through others, tracked by `state.json`.

## Important

- Watcher ignores typical generated files and environment or editor files.
- Use `README.md` as the product entrypoint.
- Use `docs/TEXTIFAI_SEMANTIC_STORY_ENGINE_ROADMAP.md` for the technical-product roadmap.
- Use `docs/ARCHITECTURE.md`, `docs/BOOTSTRAP_V1_FLOW.md`, `docs/VAULT_SCHEMA.md`, and `docs/e2e_semantic_diagnosis_rules.md` for the active TextifAI bootstrap rail.
- Use `WORKFLOW.md` and `PIPELINE.md` for the legacy AutoNovel writing pipeline.

---

This document aims to prevent mistakes by explicitly stating commands, API key needs, repo layout, and operational quirks unique to TextifAI.
