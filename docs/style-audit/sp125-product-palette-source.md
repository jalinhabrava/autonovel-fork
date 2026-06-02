# SP-125 Product Palette Source

## Source of truth

Primary source of truth: `/home/david/projects/textifai-web`.

This repo was treated as read-only. No files were edited, formatted, built, or committed there.

## Exact product-web files inspected

- `/home/david/projects/textifai-web/src/styles/global.css`
- `/home/david/projects/textifai-web/src/components/Navbar.astro`
- `/home/david/projects/textifai-web/src/components/Footer.astro`
- `/home/david/projects/textifai-web/src/pages/index.astro`
- `/home/david/projects/textifai-web/src/pages/about/index.astro`
- `/home/david/projects/textifai-web/src/pages/early-access.astro`
- `/home/david/projects/textifai-web/src/pages/login.astro`

## How palette is defined

The product-web palette is primarily defined in `/home/david/projects/textifai-web/src/styles/global.css` as CSS variables, then consumed through Astro/Tailwind utility classes in page and component files.

## Palette extraction table

| Role | Value | Source file | Source selector/class/token | Confidence | Notes |
| --- | --- | --- | --- | --- | --- |
| page/app background | `#f7f1e7` | `src/styles/global.css` | `:root --bg` | high | Primary warm paper background |
| elevated background | `#efe4d6` | `src/styles/global.css` | `:root --bg-strong` | high | Stronger warm backdrop tone |
| surface/card | `rgba(255, 251, 245, 0.88)` | `src/styles/global.css` | `:root --surface` | high | Base translucent warm surface |
| muted surface | `#fffaf3` | `src/styles/global.css` | `:root --surface-strong` | high | Used for stronger panel fill |
| border/default divider | `rgba(124, 97, 72, 0.18)` | `src/styles/global.css` | `:root --border` | high | Soft taupe divider |
| stronger border | `rgba(124, 97, 72, 0.28)` | inferred from product border | n/a | medium | Arc extension for stronger structure |
| primary text | `#211913` | `src/styles/global.css` | `:root --text` | high | Dark warm brown body ink |
| muted text | `#6f6256` | `src/styles/global.css` | `:root --muted` | high | Secondary warm gray-brown |
| subtle text | `rgba(111, 98, 86, 0.72)` | derived from `--muted` | n/a | medium | Arc extension for tertiary text |
| primary accent | `#b77a4b` | `src/styles/global.css` | `:root --accent` | high | Product-web caramel accent |
| accent hover | `#9f673d` | derived from `--accent` | n/a | medium | Arc app hover extension |
| soft accent background | `rgba(183, 122, 75, 0.14)` | `src/styles/global.css` | `:root --accent-soft` | high | Product-web soft accent wash |
| primary button background | `#2c221c` | `src/styles/global.css` | `.btn-primary background: var(--surface-ink)` | high | Product-web button uses dark ink fill |
| primary button hover | `#211913` | derived from product ink family | n/a | medium | Arc app hover extension |
| secondary button background | `rgba(255, 250, 243, 0.72)` | `src/styles/global.css` | `.btn-secondary background` | high | Product-web secondary fill |
| active nav background | `#8f5a2a` | Arc extension | n/a | medium | Needed for selected app controls |
| active nav text | `#fdf7f0` | derived from product button text | `.btn-primary color` | medium | Warm light text on dark active controls |
| focus ring | `rgba(183, 122, 75, 0.38)` | derived from `--accent` | n/a | medium | Needed for visible keyboard focus |
| danger | `#b4544f` | Arc extension | n/a | medium | Product-web does not define semantic danger |
| success | `#4f7a5c` | Arc extension | n/a | medium | Product-web does not define semantic success |
| warning | `#a16d3b` | Arc extension | n/a | medium | Product-web does not define semantic warning |
| card shadow | `0 18px 60px rgba(49, 33, 19, 0.08)` | `src/styles/global.css` | `:root --shadow` | high | Product-web panel shadow |
| radius card | `24px` | `src/styles/global.css` | `:root --radius-card` | high | Product-web card radius |
| radius button | `999px` | `src/styles/global.css` | `:root --radius-pill` | high | Product-web pill/button radius |

## Direct product-web values vs Arc extensions

### Direct product-web mappings

- `#f7f1e7`
- `#efe4d6`
- `rgba(255, 251, 245, 0.88)`
- `#fffaf3`
- `#211913`
- `#2c221c`
- `#6f6256`
- `rgba(124, 97, 72, 0.18)`
- `#b77a4b`
- `rgba(183, 122, 75, 0.14)`
- `0 18px 60px rgba(49, 33, 19, 0.08)`
- `24px`
- `999px`

### Arc app extensions

These are not explicit product-web tokens, but are needed for app interaction states the marketing site does not define fully:

- `rgba(124, 97, 72, 0.28)` stronger border
- `rgba(111, 98, 86, 0.72)` subtle text
- `#9f673d` accent hover
- `#211913` primary button hover
- `#8f5a2a` active nav / selected control background
- `#fdf7f0` active nav / action text
- `rgba(183, 122, 75, 0.38)` focus ring
- semantic danger/success/warning values for app states

## UX notes

- Warm paper backgrounds reduce pure-white fatigue in long authoring sessions.
- Dark warm brown ink keeps contrast high without collapsing into harsh black.
- Caramel accent works well for focus, CTA, and selected controls, but app surfaces need darker chocolate support for stronger operational affordance.
- Graph semantic colors should remain separate from this shell palette to preserve information scent.
