# SP124 Theme Token Candidates

Audit-only token proposal. Do not implement in this safepoint.

## Candidate Token Groups

| Candidate token | Intended meaning | Current observed sources to map |
|---|---|---|
| `--color-bg` | app/page background | `bg-neutral-50`, `#f5f1e8`, `#fffaf0`, neutral page backgrounds, landing `#0a0a08` as separate dark landing background |
| `--color-bg-elevated` | raised app regions / modal backgrounds | `bg-white`, `#ffffff`, modal/card wrappers in `App.tsx`, `common/ui.tsx`, `GraphInspector.tsx` |
| `--color-surface` | card/panel surface | `bg-white`, `bg-neutral-50`, `#fff`, `.card`, `.panel`, `.summary-card` in `static/styles.css` |
| `--color-surface-muted` | secondary/disabled surface | `bg-neutral-50`, `bg-neutral-100`, warm off-white surfaces |
| `--color-border` | default divider/border | `border-neutral-200`, `#e5e7eb`, `rgb(229 229 229)`, beige borders in static CSS |
| `--color-border-strong` | emphasized border | `border-neutral-300`, darker dividers, graph/review emphasized borders |
| `--color-text` | primary copy | `text-neutral-900`, `#111111`, `#171717`, `rgb(23 23 23)` |
| `--color-text-muted` | secondary copy | `text-neutral-500`, `text-neutral-600`, `#6b7280`, `#737373`, `rgb(82 82 82)` |
| `--color-accent` | primary action/accent | `bg-blue-600`, `text-blue-700`, `#1d4ed8`, `#0090ff`, landing `#daa548` if unified later |
| `--color-accent-hover` | primary action hover | `hover:bg-blue-700`, hover accent states, landing `#c8941e` |
| `--color-accent-soft` | low-emphasis accent bg | `bg-blue-50`, `border-blue-200`, soft accent overlays |
| `--color-danger` | destructive/error | `bg-red-50`, `text-red-700`, `border-red-200`, `#8c2240` |
| `--color-success` | success/healthy state | `bg-green-50`, `text-green-700`, `border-green-200` |
| `--shadow-card` | default card shadow | `shadow-sm`, `shadow-xl`, `shadow-2xl`, `box-shadow` rules in `static/styles.css` |
| `--radius-card` | cards/panels/modals | `rounded-xl`, `rounded-2xl`, `rounded-3xl`, CSS border-radius declarations |
| `--radius-button` | buttons/chips/controls | `rounded-lg`, `rounded-xl`, `rounded-full` depending control type |

## Current Palette Clusters

- Neutral React shell: `bg-white`, `bg-neutral-50`, `bg-neutral-100`, `border-neutral-200`, `text-neutral-500/600/700/900`.
- Blue action/info: `bg-blue-50`, `bg-blue-600`, `text-blue-700`, `border-blue-200`, `#1d4ed8`, `#0090ff`.
- Status colors: red/green/amber Tailwind classes plus `#8c2240`, red/amber overlays.
- Warm app/product colors: `#f5f1e8`, `#fffaf0`, beige/brown-like surfaces in static CSS.
- Landing dark/gold: `#0a0a08`, `#e8e4db`, `#daa548`, `#b8943e`, `#c8941e`, `#2a2820`.
- Graph semantic colors: `textifai/web_viewer/react_shell/src/graph/GraphTheme.ts` and `textifai/web_viewer/react_shell/src/graph/GraphCanvas.tsx` values should remain semantic graph-node tokens, not generic UI tokens.

## Proposed Mapping Strategy

- Keep source values initially identical; use tokens as indirection only in first migration.
- Use semantic tokens for UI chrome, and separate graph tokens for entity/node/category meaning.
- Map Tailwind theme names to CSS variables so JSX can use stable classes such as `bg-surface`, `text-muted`, `border-default`, and `bg-accent`.
- Avoid editing generated `textifai/web_viewer/static/react-shell/app.css` manually; rebuild from React shell source.
- Treat `landing/index.html` as separate migration unit because it has embedded CSS and separate dark/gold brand direction.

## Safe Migration Sequence

### Phase A

- Introduce central CSS variables / theme tokens.
- Map Tailwind theme colors to CSS vars if possible.
- Preserve current visual values and avoid global replacements.
- Add token documentation before usage migration.

### Phase B

- Migrate global backgrounds/surfaces first.
- Start with body, root shell, sidebars, page backgrounds, primary panel/card backgrounds.
- Verify contrast before migrating text colors broadly.

### Phase C

- Migrate reusable components/cards/buttons/forms.
- Prioritize `textifai/web_viewer/react_shell/src/common/ui.tsx` and shared CSS selectors in `textifai/web_viewer/static/styles.css`.
- Then update repeated modal/card/button patterns in `textifai/web_viewer/react_shell/src/App.tsx`.

### Phase D

- Remove inline hardcoded colors.
- Tokenize repeated Tailwind arbitrary values and graph-safe UI chrome.
- Leave dynamic layout inline style in `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx` unless token conversion adds clear value.

### Phase E

- Run visual regression/manual browser pass.
- Compare landing, maintenance/empty states, early access/waitlist if present, login/about/roadmap if present, project hub, graph inspector, review queue, ingestion, and modals.
- Rebuild React shell and verify generated CSS only changes as expected.

## Risk Section

- Components where changing colors may affect readability: all neutral text classes, graph inspector metadata, button contrast states, badges, alerts, disabled text.
- Pages likely to have duplicated styles: `textifai/web_viewer/react_shell/src/App.tsx`, `textifai/web_viewer/static/styles.css`, `landing/index.html`, `textifai/web_viewer/react_shell/src/common/ui.tsx`.
- Inline styles that are risky: only dynamic width in `textifai/web_viewer/react_shell/src/modules/ingestion/IngestionView.tsx:395`; low branding risk.
- Tailwind arbitrary values that should be tokenized: any future `bg-[...]`, `text-[...]`, `border-[...]`, `shadow-[...]` source usage; current generated CSS output should not be tokenization target.
- Files where source of truth is ambiguous: `textifai/web_viewer/static/react-shell/app.css` versus `textifai/web_viewer/react_shell/src/styles.css` plus TSX utility classes.
- Graph risk: semantic graph node colors should be tokenized separately from generic app palette.
- Landing risk: embedded CSS uses independent dark/gold palette and may intentionally diverge from app shell.

## Recommended Next Safepoint

`SP125 — introduce non-visual theme token scaffold`

1. Add CSS custom properties with current values.
2. Extend Tailwind theme to reference CSS variables.
3. Migrate one low-risk shared component file as proof pattern.
4. Run browser/manual contrast pass before broad page migration.

## Assessment

`style_source_audit_ready`
