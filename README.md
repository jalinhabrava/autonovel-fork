# TextifAI

TextifAI is the product/runtime identity of this repository. Under the hood,
it is still based on a fork of AutoNovel, but the product layer is now being
built and presented as TextifAI.

This repository is a fork of AutoNovel. It keeps the original idea of an
AI-assisted novel pipeline, but is being refactored into a persistent,
modular, and eventually conversational narrative system.

The long-term goal is not only "generate a novel from a seed", but to build a
story engine that combines:

- text generation
- persistent narrative memory
- canon extraction and validation
- vault-backed project storage
- interactive editing and review workflows
- configurable context assembly for future conversational interfaces

## Mission And Creative Position

This fork prioritizes a `human-created, AI-assisted` model over a purely
`AI-generated` one.

The intended role of the system is to help a human author or editor:

- structure and persist narrative knowledge
- inspect context and canon
- draft or rewrite with assistance
- review consistency and implications
- bootstrap artifacts from existing material
- accelerate editorial and production workflows

The system can generate directly when asked, but that is not the core creative
philosophy of the fork. The main aim is to support human-led storytelling,
human original ideas, and human editorial judgment with stronger tooling and
memory.

In practice, this means the project is being shaped as narrative
infrastructure for collaboration with AI, not as a machine for replacing the
author.

## What This Fork Keeps From AutoNovel

Several important parts of the original project are still present:

- the phase-based pipeline driven by [run_pipeline.py](/home/david/projects/autonovel-fork/run_pipeline.py)
- the layered artifact model:
  - `voice.md`
  - `world.md`
  - `characters.md`
  - `outline.md`
  - `canon.md`
  - `chapters/`
- generation and revision tools for world, characters, outline, drafting, review, art, and audiobook
- the original idea of iterating through generate -> evaluate -> revise loops

This means the repo still works as a recognizable AutoNovel-derived codebase,
even while the internals are being restructured.

## What Has Changed

This fork has already moved well beyond "the original pipeline plus a few
patches". The most important changes are:

- text inference is now routed through a provider abstraction instead of being hard-wired to a single hosted API
- project storage is abstracted behind a store/backend layer instead of assuming a fixed workspace layout everywhere
- an Obsidian-compatible vault system now exists as a persistent project backend
- an interactive layer now exists for:
  - context lookup
  - note creation/update
  - canon decisions
  - consistency checks
  - manuscript bootstrap extraction
- a first deterministic Context Engine now exists to assemble structured context packs from the vault

## Current Vision

The target system is a narrative infrastructure with three major properties:

1. Persistent
   Narrative knowledge should live in durable project artifacts, especially a vault-backed source of truth.

2. Modular
   Providers, storage backends, extraction flows, and context policies should be swappable without rewriting the whole pipeline.

3. Conversational
   The future user experience is not just a batch run. It is an interactive environment where a user or editor can inspect context, issue commands, validate canon, and revise notes incrementally.

Those three properties sit inside a larger creative principle:

- the human remains the authorial center
- AI acts as assistant, collaborator, critic, organizer, and accelerator
- direct generation is available, but not treated as the only or ideal mode

## Current Architecture

### Inference Layer

Text generation now runs through a shared provider layer in [providers/text_provider.py](/home/david/projects/autonovel-fork/providers/text_provider.py).

Implemented:

- Anthropic
- OpenAI
- LM Studio
- Ollama
- Anthropic-compatible endpoints
- OpenAI-compatible endpoints

Configuration lives in:

- [.env.example](/home/david/projects/autonovel-fork/.env.example)
- [config/inference.json](/home/david/projects/autonovel-fork/config/inference.json)

This lets the core pipeline change provider without rewriting the scripts that call the model.

### Project Storage Layer

Project persistence now goes through [stores/project_store.py](/home/david/projects/autonovel-fork/stores/project_store.py).

Implemented:

- workspace adapter for the classic AutoNovel layout
- vault adapter for Obsidian-style storage
- abstraction of artifacts, chapters, and pipeline state away from direct path assumptions in the core

Key files:

- [stores/project_store.py](/home/david/projects/autonovel-fork/stores/project_store.py)
- [adapters/workspace_adapter.py](/home/david/projects/autonovel-fork/adapters/workspace_adapter.py)
- [adapters/vault_adapter.py](/home/david/projects/autonovel-fork/adapters/vault_adapter.py)

### Vault / Obsidian Layer

The vault is now treated as a first-class backend and intended source of truth.

Implemented:

- official vault layout and templates
- bootstrap wizard
- layout validation
- read/write support for structured notes
- ingestion of structured payloads
- manuscript bootstrap scaffolding

Key files:

- [vault/bootstrap.py](/home/david/projects/autonovel-fork/vault/bootstrap.py)
- [vault/notes.py](/home/david/projects/autonovel-fork/vault/notes.py)
- [vault/ingest.py](/home/david/projects/autonovel-fork/vault/ingest.py)
- [docs/VAULT_SCHEMA.md](/home/david/projects/autonovel-fork/docs/VAULT_SCHEMA.md)

### Interactive Layer

The repo now has an internal interactive runtime. It is not yet LibreChat, MCP,
or a public conversational UI, but the internal command layer already exists.

Implemented:

- context lookup commands
- note creation/update commands
- canon decisions
- validate/reject transitions
- consistency guardrails before persistence
- bootstrap extraction from existing manuscript chapters

Key files:

- [interactive/context_commands.py](/home/david/projects/autonovel-fork/interactive/context_commands.py)
- [interactive/persistence_commands.py](/home/david/projects/autonovel-fork/interactive/persistence_commands.py)
- [interactive/bootstrap_extract.py](/home/david/projects/autonovel-fork/interactive/bootstrap_extract.py)

Important limitation:

`consistency-check` is currently a minimum persistence guardrail. It does not
replace full editorial review, reader review, or a future advanced consistency
system.

### Context Engine V1

A first internal Context Engine now exists.

Implemented:

- deterministic intent resolution
- explicit `narrative_scope` vs `retrieval_scope`
- structured candidate retrieval from the vault
- explainable ranking with score breakdowns
- configurable context policies
- structured `context_pack` output with:
  - `hard_constraints`
  - `narrative_context`
  - `voice_context.project_voice`
  - `voice_context.character_voice`
  - `evidence`

Key files:

- [context_engine/contracts.py](/home/david/projects/autonovel-fork/context_engine/contracts.py)
- [context_engine/query.py](/home/david/projects/autonovel-fork/context_engine/query.py)
- [context_engine/ranking.py](/home/david/projects/autonovel-fork/context_engine/ranking.py)
- [context_engine/builder.py](/home/david/projects/autonovel-fork/context_engine/builder.py)
- [context_engine/service.py](/home/david/projects/autonovel-fork/context_engine/service.py)
- [config/context_policies.json](/home/david/projects/autonovel-fork/config/context_policies.json)

Not implemented yet:

- embeddings
- semantic/vector retrieval
- external chat integration
- advanced compression profiles

## What Is Already Implemented

The following are real, present features in the repo today:

- text provider abstraction with hosted and local backends
- project store abstraction
- vault bootstrap, schema, and adapter
- interactive persistence primitives
- manuscript bootstrap extractors:
  - `extract-voice`
  - `extract-characters`
  - `extract-canon`
  - `extract-timeline`
- deterministic Context Engine v1
- policy-driven context assembly
- tests for providers, storage, vault, interactive layer, bootstrap, and context engine

## What Is Still Future Work

The project is intentionally mid-refactor. These areas are still future or only partially built:

- LibreChat integration
- MCP integration
- external conversational interface
- advanced editorial review flows built on top of the interactive layer
- richer voice preset system
- full semantic bootstrap from an existing novel
- embeddings / semantic retrieval
- more advanced context policies and compression strategies
- broader cleanup of remaining legacy scripts outside the main refactor path

## Providers

The default text provider is configured through `AUTONOVEL_TEXT_PROVIDER`.

Supported values currently include:

- `anthropic`
- `openai`
- `lmstudio`
- `ollama`
- `anthropic_compatible`
- `openai_compatible`

Task-level defaults and overrides live in [config/inference.json](/home/david/projects/autonovel-fork/config/inference.json).

This fork is explicitly designed to keep hosted providers working while opening
the door to local backends.

## Vault Usage

The project backend can target either the classic workspace layout or a vault.

Environment selection:

```bash
AUTONOVEL_PROJECT_BACKEND=workspace
```

or:

```bash
AUTONOVEL_PROJECT_BACKEND=vault
AUTONOVEL_VAULT_ROOT=/absolute/path/to/your/vault
```

Useful vault commands:

```bash
uv run python main.py init-vault --path /tmp/MyNovelVault --title "My Novel"
uv run python main.py validate-vault --path /tmp/MyNovelVault
uv run python main.py export-context --path /tmp/MyNovelVault --artifact all
uv run python main.py import-existing-chapters --path /tmp/MyNovelVault --source-dir ./legacy_chapters
uv run python main.py ingest-context --path /tmp/MyNovelVault --json ./digested_context.json
```

See [docs/VAULT_SCHEMA.md](/home/david/projects/autonovel-fork/docs/VAULT_SCHEMA.md) for the schema and note model.

## Bootstrap From Existing Manuscript

The repo can now bootstrap project artifacts from chapters already written.

Implemented extractors:

- `interactive-extract-voice`
- `interactive-extract-characters`
- `interactive-extract-canon`
- `interactive-extract-timeline`

Current behavior:

- generated artifacts persist as `proposed` or `pending_revision`
- never `validated` by default
- `origin.source` is set to `manuscript_bootstrap`
- `origin.chapter_ids` are recorded when available
- bootstrap prefers creating new proposals over overwriting sensitive notes

Important limitation:

These extractors are deliberately heuristic and conservative. They are meant to
seed a project with traceable proposals, not to perform final editorial or
canonical judgment.

## Quick Start

```bash
git clone <repo-url>
cd textifai
cp .env.example .env
uv sync
```

If you want the classic pipeline flow:

```bash
uv run python run_pipeline.py --from-scratch
```

If you want a vault-backed project:

```bash
textifai setup
```

Product entrypoints:

```bash
textifai
textifai chat
textifai setup
textifai doctor
```

## Main Commands

Pipeline:

```bash
uv run python run_pipeline.py --phase foundation
uv run python run_pipeline.py --phase drafting
uv run python run_pipeline.py --phase revision
uv run python run_pipeline.py --phase export
```

Interactive / vault:

```bash
uv run python main.py interactive-world --path /tmp/MyNovelVault
uv run python main.py interactive-find --path /tmp/MyNovelVault --query "Sera"
uv run python main.py interactive-consistency-check --path /tmp/MyNovelVault --json payload.json
uv run python main.py interactive-create-note --path /tmp/MyNovelVault --json payload.json
uv run python main.py interactive-update-note --path /tmp/MyNovelVault --json payload.json
```

Bootstrap:

```bash
uv run python main.py interactive-extract-voice --path /tmp/MyNovelVault --chapter-from 1 --chapter-to 3
uv run python main.py interactive-extract-characters --path /tmp/MyNovelVault --chapter-id ch_01 --chapter-id ch_02
uv run python main.py interactive-extract-canon --path /tmp/MyNovelVault --chapter-id ch_03
uv run python main.py interactive-extract-timeline --path /tmp/MyNovelVault --chapter-id ch_04
```

## Current Boundaries

This README intentionally describes the current system honestly:

- the fork is already much more than the original AutoNovel pipeline
- the persistent vault architecture is real
- the interactive layer is real
- the Context Engine v1 is real
- the project is being oriented toward human-led creation with AI assistance, not toward fully autonomous authorship as its primary mode
- the future conversational shell is not implemented yet
- embeddings are not implemented yet
- advanced editorial orchestration on top of the new layers is still in progress

## Related Docs

- [PIPELINE.md](/home/david/projects/autonovel-fork/PIPELINE.md)
- [WORKFLOW.md](/home/david/projects/autonovel-fork/WORKFLOW.md)
- [docs/VAULT_SCHEMA.md](/home/david/projects/autonovel-fork/docs/VAULT_SCHEMA.md)
- [docs/TODO_PHASE1.md](/home/david/projects/autonovel-fork/docs/TODO_PHASE1.md)
- [docs/ARCHITECTURE_NOTES.md](/home/david/projects/autonovel-fork/docs/ARCHITECTURE_NOTES.md)

## Inspiration

- the original AutoNovel project and workflow
- [karpathy/autoresearch](https://github.com/karpathy/autoresearch)
- story development and revision frameworks carried over from the original codebase
