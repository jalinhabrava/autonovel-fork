# Vault Schema

## Goal

The vault should support one simple bootstrap loop well:

- source documents in
- chapter-level extraction
- entity merge
- canonical primaries out
- review kept separate

The vault is not meant to encode a giant semantic ontology. It should stay readable in Obsidian and useful for VaERL.

## Directory Layout

```text
00_Project/
01_Voice/
02_World/
  Places/
  Magic/
  Creatures/
  Factions/
  Objects/
  History/
  Lore/
03_Characters/
  Profiles/
04_Story/
  Chapters/
  Chapter_Summaries/
05_Draft/
06_Canon/
07_Editorial/
90_Review/
99_Import_Staging/
99_System/
_Templates/
```

## Canonical Note Roles

Visible and useful roles:

- `primary`
- `chapter`
- `chapter_summary`

Hidden operational role:

- `review`

## Minimum Bootstrap Metadata

Canonical notes should carry enough metadata for Obsidian and VaERL, but no more than needed:

```yaml
---
kind: character
title: Sera
status: pending_revision
schema_version: 1.0
slug: sera
note_role: primary
entity_kind: character
canonical_subject: Serélyne Thiseriya d’Aelwen
aliases:
  - Sera
  - Serelyne
review_state: canonical
confidence: 0.92
evidence_sources:
  - /path/to/source.md
tags:
  - '#primary'
---
```

Recommended fields:

- `kind`
- `title`
- `status`
- `schema_version`
- `slug`
- `note_role`
- `entity_kind`
- `canonical_subject`
- `aliases`
- `review_state`
- `confidence`
- `evidence_sources`
- `tags`

## Hidden Material

Review and staging remain important, but must stay out of the useful graph and out of normal retrieval.

Expected tags:

- review/staging: `#review`
- chapter/chapter_summary: `#chapters`
- system: `#system`
- primary: `#primary`

Expected behavior:

- `90_Review` is for unresolved material
- `99_Import_Staging` is internal bootstrap workspace
- `99_System` is operational output only

## Retrieval Policy

Normal retrieval should prefer:

1. exact canonical primaries
2. nearby canonical primaries
3. chapter summaries
4. chapters

Review and staging are not normal retrieval targets.

## V1 Constraint

The current V1 should be treated as Markdown-first.

The decisive capability is not “can we ingest every format,” but “can we reliably build canonical primaries from chapter-level structured outputs and merged entities.”
