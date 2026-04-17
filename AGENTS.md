# AGENTS

This file contains essential instructions for working effectively with the autonovel repository.

---

## Setup

- Always start by copying `.env.example` to `.env` and filling in required API keys.
  - `ANTHROPIC_API_KEY` is mandatory.
  - `FAL_KEY` and `ELEVENLABS_API_KEY` are optional for art and audiobook features.
- Use `uv run python <script.py>` to execute Python scripts (not plain `python`).
- The main orchestrator is `run_pipeline.py`.

## Main Commands

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

- Ask for permission before running bash commands or editing files.
- Watcher ignores typical generated files and environment or editor files.
- There are no CI workflows or tests in this repo.
- Use `WORKFLOW.md` and `PIPELINE.md` for detailed human and technical pipeline guidance.

---

This document aims to prevent mistakes by explicitly stating commands, API key needs, repo layout, and operational quirks unique to autonovel.