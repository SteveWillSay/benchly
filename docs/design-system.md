# Design system

Benchly's UI is hand-written CSS — no framework, no build step. But it isn't ad hoc: there's
a deliberate token set and a small component vocabulary, declared at the top of
[`ui/css/app.css`](../ui/css/app.css). This doc writes that system down so it stays consistent
release to release, and is honest about where it has drifted.

The house style: **flat surfaces, hairline borders, one accent, base-4 spacing, dark-first.**

## Tokens

All tokens live in `:root` in `app.css`. Themes (see below) override the *values*, never the
names — so everything downstream just reads the token.

| Group | Tokens | Notes |
|---|---|---|
| **Surfaces** | `--canvas` `--surface` `--raised` `--overlay` | Flat, no gradients. Darkest → lightest. |
| **Borders** | `--border-1/2/3` | Alpha-white hairlines, so they sit on any surface. |
| **Text** | `--text-1/2/3` | Primary / secondary / tertiary. |
| **Brand & accent** | `--brand-grad` `--accent` `--accent-text` `--accent-bg` `--on-accent` | Warm sunset gradient for brand moments; a single solid `--accent` for UI. |
| **Status** | `--ok` `--warn` `--crit` `--info` `--unk` (each with a `-bg`) | Desaturated, dark-tuned. |
| **Chart series** | `--cpu` `--ram` `--dsk` `--net` | Fixed per-metric colours. |
| **Radii** | `--r1` (6px, controls/chips/inputs) `--r2` (10px, cards/panels/modals) | |
| **Shadow** | `--shadow-overlay` | The one elevation — overlays/popovers. |
| **Type** | `--font` `--font-display` `--mono` | Body / condensed display / mono. |

### Type scale

Sizes are raw `px` (there are no size tokens yet). The intended scale is **11 / 12 / 13 / 14 /
16 / 20**, with `13px` as the body default. Two display headings use **30/32**. (The original
header comment claims `…/28`; in practice 30/32 are used — the comment is stale, fix one or the
other.) Keep new type on the scale; reach for `--font-display` only for headings and brand.

## Components

The working vocabulary, all in `app.css`:

| Component | Variants | States covered |
|---|---|---|
| **Button** `.btn` | `.primary` `.ghost` `.danger` (+`.danger.solid`), `.small` | hover, active, disabled, focus-visible |
| **Nav item** `.nav-item` | active | hover, active |
| **Pill / chip** `.pill` `.chip` | status colours via `--ok/warn/crit/info/unk` | — |
| **Toggle** `.switch` | on/off | — |
| **Card / panel** `.card` `.table-wrap` | — | — |
| **Table** | sortable, filterable, row-hover actions | hover |
| **Toast** `.toast` | info / bad / good | timed dismiss |
| **Modal** `.modal` + `#palette` | — | open/close |
| **Empty state** `.empty` | icon + title + hint | — |

Global: `:focus-visible` draws a 2px `--accent` ring everywhere — keep it.

## Theming

Themes are pure token overrides keyed off an attribute on `<html>`:

```css
html[data-theme="frost"] { --canvas: …; --surface: …; /* same token names, new values */ }
```

`ui/css/theme-frosted-glass.css` redefines the full token set (plus a few `--ic-*` glass
extras). To add a theme: copy that file, change the `data-theme` key and the values — never
introduce new component CSS in a theme, only token values.

## Known gaps (audit backlog)

Scored **~78/100** — strong tokenisation, weak accessibility. In rough priority:

1. **`prefers-reduced-motion` is not honoured anywhere.** Sparklines, transitions and the
   nav animations all run regardless. Add a `@media (prefers-reduced-motion: reduce)` block
   that drops non-essential motion. *(Highest impact, lowest effort.)*
2. **Icon-only buttons lack accessible names.** ~228 `<button>`s, but only `title=` (a tooltip,
   not a reliable accessible name) and almost no `aria-label`. Add `aria-label` to icon buttons.
3. **Type sizes aren't tokenised** and the scale has drifted (9/10/15/32 sneak in). Introduce
   `--fs-*` tokens and snap strays back onto the scale.
4. **Pill radius `999px` isn't a token** (used in ~8 places). Add `--r-pill: 999px`.
5. **`.btn.danger.solid` hardcodes `#c93f38`/`#d8473f`.** Promote to `--crit-solid` /
   `--crit-solid-hover` so the danger colour has one source of truth.

> Not a gap: the ~19 hex literals in `app.js` are the theme **background-preset** swatches —
> that's data, not chrome, and belongs inline.
