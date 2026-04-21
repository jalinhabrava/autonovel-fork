# TextifAI

TextifAI is the core product/runtime of this repository. It was born from an AutoNovel fork, but it is no longer best described as "just a fork". The codebase now centers on a vault-aware narrative system with a terminal runtime, structured conversational interpretation, editorial structuring, and context preparation for later narration and review.

The project still preserves the original AutoNovel lineage and pipeline ideas, but the current product direction is broader and more explicit:

- a human-led writing workflow
- persistent narrative memory
- vault-backed source of truth
- conservative resolution against real project artifacts
- structured editorial outputs instead of raw prompt juggling
- a runtime that can support future conversational and review loops without becoming magical

## What TextifAI Is Today

TextifAI is the layer that sits above the vault and gives the author a usable workflow:

- it interprets author input
- it resolves mentions against the vault
- it selects and prepares context
- it structures editorial output
- it prepares context for narration later
- it keeps the system conservative when it cannot resolve something safely

Obsidian and the vault provide the durable project memory. TextifAI does the interpretation, anchoring, selection, and workflow control on top of that memory.

## Vault And TextifAI

The vault is the single source of truth for project knowledge:

- notes
- titles
- slugs
- aliases
- links and backlinks
- metadata
- document structure
- canonical artifacts

TextifAI does not replace that source of truth. It adds a working layer on top of it:

- conversational context extraction
- vault-aware entity resolution
- editorial structuring
- narration preparation
- deterministic context assembly
- controlled persistence and review flows

Obsidian/vault stores the facts and relationships. TextifAI interprets them and chooses what to do next.

## Core Layers

### CCE

Conversational Context Extraction (CCE) is the part that reads the author input and identifies what kind of request it is.

CCE looks for:

- intent
- follow-up behavior
- narrative signals
- editorial signals
- hints about the expected target or artifact type

CCE does not try to be the whole system. It interprets the input. VaERL and the editorial layers then act on that interpretation.

### VaERL

The Vault-aware Entity Resolution Layer (VaERL) resolves or suggests anchors against the vault.

It separates:

- detected mentions
- candidate entities
- final resolution
- confidence
- related artifact suggestions

VaERL is conservative by design. If it cannot resolve safely, it prefers candidates or no resolution over false certainty.

### Editorial Structuring

Editorial structuring turns author input into usable intermediate structures such as:

- `StoryFacts`
- `BeatOutline`
- `RevisionIntent`
- `EditorialStructuringResult`

This layer is the bridge between raw language and a workflow the author can validate.

### Narration Prep

Narration prep prepares context for later narration. It does not narrate yet.

It can be built from:

- `BeatOutline`
- `StoryFacts`
- `RevisionIntent`
- previous editorial output

Its job is to gather the right context, voice, canon, continuity, and language constraints before any stronger narration step happens.

### Context Engine

The Context Engine assembles structured context packs from the vault.

It is different from VaERL:

- VaERL resolves and anchors
- Context Engine packages context

That separation matters. We do not want duplicate retrieval logic in multiple places.

## How The Flow Works

The current workflow is:

1. the author writes something in natural language
2. CCE classifies the request
3. VaERL resolves mentions against the vault when possible
4. editorial structuring turns the input into a usable shape
5. context preparation selects the useful project artifacts
6. the system returns a structured result the author can validate
7. later stages can use that structure for narration or review

This is intentionally not a fully autonomous authoring loop. The human remains the authorial center.

## Repository Scope

This repository contains the current open core of TextifAI. It is the working
codebase for the product as it exists today, and it is intentionally local-first
and vault-aware.

The scope here includes:

- terminal runtime
- conversational interpretation
- vault-aware entity resolution
- editorial structuring
- narration preparation
- Context Engine
- persistence and validation primitives
- core pipeline orchestration

Some later layers may live outside this repository or in adjacent private
workflows, depending on how the product evolves. Those future layers may cover
things like:

- richer collaborative UX
- advanced hosted workflows
- more opinionated editorial automation
- private deployment-specific enhancements

That future work is not part of the present core. The current repository should
be read on its own terms, as the product layer that already exists and runs
today.

## Current Architecture At A Glance

- `textifai/`
  - product/runtime layer
  - conversation
  - editorial intent
  - editorial structuring
  - narration prep
  - VaERL
  - terminal entrypoints
- `context_engine/`
  - deterministic context assembly
- `vault/`
  - vault schema, bootstrap, read/write, ingest
- `interactive/`
  - internal context and persistence commands
- `providers/`
  - inference backend abstraction
- `stores/`
  - project storage abstraction
- `scripts/`
  - operational entrypoints grouped by task family

## What Is Already Implemented

The repo already includes:

- a provider abstraction for hosted and local models
- a project storage abstraction
- a vault backend and schema
- a terminal TextifAI runtime
- interactive context and persistence commands
- a deterministic Context Engine
- runtime language policy support
- conversational intent and task scaffolding
- CCE and editorial intent classification
- VaERL
- editorial structuring contracts and builders
- narration prep contracts and builders

## What Is Still Future Work

Not yet implemented, or still intentionally limited:

- GUI
- LibreChat
- MCP
- embeddings / semantic retrieval
- advanced autonomous editing loops
- automatic narration as a mature end-state
- premium/private layers

## Quick Start

```bash
git clone <repo-url>
cd autonovel-fork
cp .env.example .env
uv sync
```

For the terminal runtime:

```bash
textifai
```

For the pipeline:

```bash
uv run python run_pipeline.py --from-scratch
```

For setup and diagnostics:

```bash
textifai setup
textifai doctor
```

## Useful Docs

- [docs/BOOTSTRAP_V1_FLOW.md](/home/david/projects/autonovel-fork/docs/BOOTSTRAP_V1_FLOW.md)
- [docs/VAULT_SCHEMA.md](/home/david/projects/autonovel-fork/docs/VAULT_SCHEMA.md)
- [WORKFLOW.md](/home/david/projects/autonovel-fork/WORKFLOW.md)
- [PIPELINE.md](/home/david/projects/autonovel-fork/PIPELINE.md)

## Honest Boundary

TextifAI is not a magical narrator and not a generic chat wrapper. The project is designed to be:

- vault-aware
- conservative
- structured
- explainable
- usable from the terminal first

The core is intentionally domain-agnostic. Example fixtures from a fantasy vault are useful for validation, but they are not the logic of the system.
