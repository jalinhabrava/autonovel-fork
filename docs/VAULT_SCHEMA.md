# Vault Schema

## Goal

The vault is the persistent source of truth for a narrative project. It must be:

- readable by Obsidian,
- writable by the pipeline,
- safe for partial bootstrap from an existing manuscript,
- and structured enough to reconstruct logical artifacts such as `world`, `characters`, `canon`, `voice`, and `outline`.

## Directory Layout

```text
00_Project/
  Project.md
  Seed.md
  Mystery.md
01_Voice/
  Voice.md
02_World/
  World.md
  Lore/
03_Characters/
  Characters.md
  Profiles/
04_Outline/
  Outline.md
  Scenes/
05_Draft/
  Manuscript.md
  Chapters/
06_Canon/
  Canon.md
  Decisions/
07_Editorial/
  Revision_Briefs/
  Reviews/
  Reader_Panel/
  Logs/
  Evaluations/
99_System/
  state.json
  results.tsv
_Templates/
```

## Root Notes

These are the top-level notes the pipeline can map back to its logical artifacts:

- `00_Project/Seed.md`
- `01_Voice/Voice.md`
- `02_World/World.md`
- `03_Characters/Characters.md`
- `04_Outline/Outline.md`
- `06_Canon/Canon.md`
- `07_Editorial/Reader_Panel/Arc_Summary.md`
- `05_Draft/Manuscript.md`

## Note Statuses

Every structured note should support:

- `proposed`
- `pending_revision`
- `validated`
- `discarded`

This is required so a future bootstrap from an existing manuscript can populate notes without marking everything as canon immediately.

## Minimum Frontmatter

All structured notes should include at least:

```yaml
---
kind: character
title: Cass Bellwright
status: proposed
schema_version: 1.0
slug: cass_bellwright
source: manual
---
```

Minimum common fields:

- `kind`
- `title`
- `status`
- `schema_version`

Common optional fields:

- `slug`
- `source`
- `chapter`

## Logical Reconstruction

The vault adapter reconstructs logical views from:

- root notes plus lore notes for `world`
- root notes plus profile notes for `characters`
- root notes plus scene notes for `outline`
- root notes plus canon decision notes for `canon`

Discarded notes are ignored in reconstructed views.

## Responsibility Split

The vault adapter is intentionally storage-oriented:

- it reads and writes Markdown notes,
- maintains the canonical vault layout,
- and reconstructs logical views such as `world`, `characters`, `outline`, and `canon`.

Semantic digestion should live outside the adapter. The intended flow is:

1. a reader or operator interacts through an Obsidian-facing CLI or interactive workflow,
2. that workflow digests manuscript context into structured payloads,
3. the vault ingestion layer persists those payloads with provenance and review status,
4. the pipeline consumes the reconstructed logical views.

This keeps storage concerns separate from higher-level editorial reasoning.

## Provenance And Partial Bootstrap

Structured notes may include richer provenance fields during bootstrap from an existing manuscript or an external interactive workflow:

- `source`
- `source_path`
- `source_chapters`
- `source_span`
- `origin_type`
- `origin_ref`
- `import_status`

These fields let the system track whether a note was manually created, imported from an existing draft, or proposed by a future Obsidian CLI without forcing immediate canon validation.

## Ingestion Payload Format

The `ingest-context` entrypoint accepts a JSON payload produced by an external workflow. Example:

```json
{
  "source_id": "obsidian-session-2026-04-17",
  "artifacts": [
    {
      "artifact": "world",
      "title": "World",
      "status": "pending_revision",
      "body": "Working synthesis from chapters 1-3.",
      "metadata": {
        "source": "obsidian_cli",
        "source_chapters": "1-3",
        "origin_type": "interactive_digest"
      }
    },
    {
      "artifact": "character",
      "slug": "mara",
      "title": "Mara",
      "status": "proposed",
      "body": "Unverified profile extracted from the draft.",
      "metadata": {
        "source": "obsidian_cli",
        "source_chapters": "2",
        "origin_type": "interactive_digest"
      }
    }
  ]
}
```

The ingestion layer persists this payload. It does not decide whether the extracted content is semantically correct; that responsibility remains with the interactive workflow and subsequent review steps.

## Current Commands

The current implementation exposes:

- `init-vault`
- `validate-vault`
- `write-note`
- `update-note`
- `export-context`
- `ingest-context`
- `import-existing-chapters`
