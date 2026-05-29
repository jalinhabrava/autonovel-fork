# SP-113A — MDXEditor Chapter Editing Spike

## Scope
- Experimental MDXEditor integration in Editor center panel.
- Chapter source remains `chapter_manifest`-driven list.
- No write-back, no patch queue, no semantic reanalysis.

## License / Dependency Result
- Candidate: `@mdxeditor/editor`.
- License: MIT (compatible).
- Added dependency only in React shell package.
- Selected plugins: headings, lists, quote, link, thematic-break, markdown-shortcuts, toolbar.

## Roundtrip Result
- Added synthetic fixture at `tests/fixtures/textifai/mdxeditor_spike/markdown_roundtrip_input.md`.
- Contract report documents mandatory preservation: frontmatter, wikilinks, headings, unicode (JP + ES accents), URL, thematic break.
- Allowed non-destructive formatting drift documented.

## UI Integration Result
- Left chapter rail unchanged (manifest-backed).
- Center panel now has experimental MDXEditor rich mode + source preview toggle.
- Right context panel preserved.
- Fullscreen behavior preserved.
- Save disabled with explicit copy: “Guardar llegará en SP-113B”.

## Limitations
- No persistence in this phase by design.
- Source mode currently read-only preview, not writable source editor.
- Roundtrip verified at contract/fixture level in this spike.

## Decision
- Assessment: `mdxeditor_spike_go_with_source_mode_constraint`.

## Recommendation for SP-113B
- Add guarded write-back path behind explicit feature flag.
- Run end-to-end markdown roundtrip test through actual editor serialization.
- Add explicit frontmatter/wikilink normalization policy before persistence.
