# SP124 Style Source Inventory

Audit-only safepoint for TextifAI Arc visual-branding source cleanup. No visual redesign, product code, route, copy, form, API, or Tailwind changes made.

## Summary

Styles currently live in four main places:

1. Global/static CSS for legacy viewer at `textifai/web_viewer/static/styles.css`.
2. React shell Tailwind source styles at `textifai/web_viewer/react_shell/src/styles.css` plus dense Tailwind utility strings in TSX.
3. Built React shell CSS artifact at `textifai/web_viewer/static/react-shell/app.css`; generated output, not source-of-truth.
4. Standalone landing HTML at `landing/index.html`, with large embedded CSS block and hardcoded dark/gold palette.

Tailwind is present, but `textifai/web_viewer/react_shell/tailwind.config.js` has no extended theme tokens yet. Most product surfaces use ad hoc Tailwind neutrals, blues, reds, greens, amber accents, shadows, and borders inline in JSX class strings.

## Required Search Coverage

Commands used included ripgrep searches for:

- CSS/SCSS files: `*.css`, `*.scss`
- Astro/HTML files: `*.astro`, `*.html`, `style=`
- React/TS files: `*.tsx`, `*.ts`, `style={{ ... }}`
- hardcoded colors: `#[0-9a-fA-F]{3,8}`, `rgba?\(`, `hsla?\(`
- CSS variables: `var\(--`, `--[a-zA-Z0-9-]+:`
- Tailwind utilities: `bg-`, `text-`, `border-`, `ring-`, `shadow-`, `from-`, `to-`, `via-`
- arbitrary utilities: `\[#[0-9a-fA-F]`, `bg-[`, `text-[`, `border-[`, `shadow-[`

## Global CSS Files

- `textifai/web_viewer/static/styles.css` — largest first-party style source; legacy/static viewer layout, cards, graph, review queue, alerts, forms, buttons, empty states, responsive rules.
- `textifai/web_viewer/react_shell/src/styles.css` — React shell Tailwind entry, base typography, small global content/prose styles.
- `textifai/web_viewer/static/react-shell/app.css` — generated Tailwind/Vite build artifact; high color count but not source-of-truth.
- `typeset/epub_style.css` — EPUB styling; out of main product-web scope unless book output branding is later included.

No `*.scss` files found.

## Tailwind Config Files

- `textifai/web_viewer/react_shell/tailwind.config.js` — content scans `./src/**/*.{ts,tsx}`; `theme.extend` is empty.
- `textifai/web_viewer/react_shell/postcss.config.js` — standard Tailwind/PostCSS bridge.

Current Tailwind source-of-truth is utility usage in TSX, not theme configuration.

## Astro / HTML Style Sources

No `*.astro` files found in audited source set.

HTML style sources:

- `landing/index.html` — embedded CSS with hardcoded dark/gold product landing palette; likely main landing page styles.
- `textifai/web_viewer/static/index.html` — static app mount shell; no meaningful color source detected.

## Inline Styles

Only one inline style occurrence found:

- `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx:395` — progress bar width uses `style={{ width: `${ingestProgressPercent}%` }}`. Dynamic layout state, not visual color; keep inline or convert to CSS custom property later.

No broad inline `style="..."` color usage found.

## Files With Hardcoded Colors

Primary files with hardcoded hex/rgb/rgba colors:

- `textifai/web_viewer/static/styles.css`
- `textifai/web_viewer/static/react-shell/app.css` (generated artifact)
- `landing/index.html`
- `textifai/web_viewer/react_shell/src/graph/GraphTheme.ts`
- `textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx`
- `textifai/web_viewer/react_shell/src/styles.css`
- `typeset/epub_style.css`

Hardcoded colors also appear indirectly via Tailwind utilities in most React shell TSX files. Full machine-readable inventory lives in `docs/style-audit/sp124-hardcoded-colors.json`.

## Dense Tailwind Color-Class Files

Dense Tailwind color/surface utility usage found in:

- `textifai/web_viewer/react_shell/src/App.tsx`
- `textifai/web_viewer/react_shell/src/common/ui.tsx`
- `textifai/web_viewer/react_shell/src/shell/AppShell.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphNodeEditDraftModal.tsx`
- `textifai/web_viewer/react_shell/src/graph/GraphToolbar.tsx`
- `textifai/web_viewer/react_shell/src/modules/canon/EntityFicheView.tsx`
- `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx`
- `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx`
- `landing/index.html`

Common repeated utility families include `bg-white`, `bg-neutral-50`, `bg-neutral-100`, `border-neutral-200`, `text-neutral-500`, `text-neutral-600`, `text-neutral-700`, `text-neutral-900`, `bg-blue-50`, `text-blue-700`, `border-blue-200`, `bg-red-50`, `text-red-700`, `bg-green-50`, and `text-green-700`.

## Top 10 Styling / Color Hotspots

Counts combine unique hardcoded colors, Tailwind utilities, and inline style occurrences from audited files.

| Rank | File | Count |
|---:|---|---:|
| 1 | `textifai/web_viewer/static/react-shell/app.css` | 259 |
| 2 | `textifai/web_viewer/static/styles.css` | 133 |
| 3 | `textifai/web_viewer/react_shell/src/App.tsx` | 64 |
| 4 | `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx` | 24 |
| 5 | `textifai/web_viewer/react_shell/src/modules/canon/EntityFicheView.tsx` | 22 |
| 6 | `textifai/web_viewer/react_shell/src/shell/AppShell.tsx` | 20 |
| 7 | `landing/index.html` | 17 |
| 8 | `textifai/web_viewer/react_shell/src/common/ui.tsx` | 15 |
| 9 | `textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx` | 10 |
| 10 | `textifai/web_viewer/react_shell/src/graph/GraphTheme.ts` | 9 |

Note: `textifai/web_viewer/static/react-shell/app.css` is generated and should be excluded from source edits except when rebuilt from React shell source.

## Brittle Color-Change Areas

- React shell JSX class strings are highly brittle because cards, buttons, panels, alerts, and text states repeat utility palettes per component.
- `textifai/web_viewer/react_shell/src/App.tsx` mixes page composition, modals, legacy embeds, error states, and panel surfaces, making global color changes easy to miss.
- `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx` and graph TS files mix semantic graph colors, badge/status colors, surfaces, and borders.
- `textifai/web_viewer/static/styles.css` centralizes many legacy viewer visuals, but it has many one-off color values and component-specific selectors.
- `landing/index.html` has independent embedded CSS and does not share React shell or legacy viewer tokens.
- Generated `textifai/web_viewer/static/react-shell/app.css` contains many colors but should not be used as source; edits there would be overwritten.

## Likely Style Sources By Surface

- Cards / panels: `textifai/web_viewer/static/styles.css`, `textifai/web_viewer/react_shell/src/common/ui.tsx`, `textifai/web_viewer/react_shell/src/App.tsx`, `textifai/web_viewer/react_shell/src/graph/GraphInspector.tsx`, `textifai/web_viewer/react_shell/src/modules/canon/EntityFicheView.tsx`.
- Buttons / CTAs: `textifai/web_viewer/static/styles.css`, `textifai/web_viewer/react_shell/src/common/ui.tsx`, `textifai/web_viewer/react_shell/src/App.tsx`, `landing/index.html`.
- Forms / inputs: `textifai/web_viewer/static/styles.css`, `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx`, `textifai/web_viewer/react_shell/src/common/ui.tsx`.
- Hero / landing: `landing/index.html`; possible product-shell overview/landing equivalents in `textifai/web_viewer/react_shell/src/App.tsx` and `textifai/web_viewer/react_shell/src/modules/project/ProjectHubView.tsx`.
- Backgrounds / app chrome: `textifai/web_viewer/static/styles.css`, `textifai/web_viewer/react_shell/src/shell/AppShell.tsx`, `textifai/web_viewer/react_shell/src/styles.css`.
- Maintenance / empty states: likely `textifai/web_viewer/static/styles.css` for legacy viewer; React empty and loading states mostly in `App.tsx`, `ProjectHubView.tsx`, `IngestionView.tsx`, and graph/review modules.
- Login / about / roadmap: no distinct source routes found in current audit; likely embedded in existing static/landing/app pages or not present in current repo snapshot.
- Early access / waitlist form: no dedicated Brevo/form implementation found in product-web search; if present externally, it is not in audited source files. Landing CTA styles live in `landing/index.html`.

## Recommended Migration Order

1. Define central theme tokens without changing rendered values.
2. Wire Tailwind theme colors to CSS variables in `textifai/web_viewer/react_shell/tailwind.config.js` while preserving current classes during transition.
3. Migrate app backgrounds and broad surfaces first: body, app shell, sidebar, panels.
4. Migrate reusable components next: `textifai/web_viewer/react_shell/src/common/ui.tsx`, common buttons, cards, inputs, badges.
5. Migrate dense page files: `textifai/web_viewer/react_shell/src/App.tsx`, graph inspector, entity fiche, ingestion/project views.
6. Migrate graph semantic colors separately from UI chrome tokens, because graph node colors encode meaning.
7. Migrate `landing/index.html` last or split it into shared CSS tokens first; it currently uses separate dark/gold palette.
8. Rebuild React shell and confirm generated `textifai/web_viewer/static/react-shell/app.css` changes only through build output.

## Audit Counts

- Unique hardcoded color values found: 298
- Tailwind utility classes found: 112
- Inline style occurrences found: 1
- Assessment: `style_source_audit_ready`
