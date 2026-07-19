# Contributing

## Styling: Tachyons first

This Hugo site uses [Ananke v2](https://ananke-documentation.netlify.app/), which already bundles [Tachyons](https://tachyons.io/). **Layout, spacing, typography, colors, borders, and responsive variants must use Tachyons utility classes.**

Do not:

- Add a separate Tachyons (or other CSS framework) dependency
- Edit theme or Hugo module-cache CSS
- Introduce new semantic/custom CSS classes for layout or formatting that Tachyons can express

### Prefer utilities in templates

Apply classes directly in project layouts and shortcodes under `layouts/`. Examples already used on this site:

| Purpose | Example utilities |
|---|---|
| Responsive column widths | `w-100 w-50-m w-third-l` |
| Spacing | `ph3 ph5-ns pv4 mb4` |
| Type scale / weight | `f3 f5 fw6 lh-copy lh-title` |
| Color | `navy mid-gray white bg-blue hover-bg-dark-blue` |
| Borders / radius | `ba b--black-10 br2 br3` |
| Flex layout | `flex flex-wrap items-center flex-none` |
| Buttons | `dib f5 fw6 tc no-underline white bg-blue hover-bg-dark-blue pv3 ph4 br2` |
| Block button | add `db w-100` |
| Cards / media chrome | `ba b--black-10` (not heavy shadows) |
| Hide/show by breakpoint | `dn db-l` |

Breakpoint suffixes follow Tachyons / Ananke:

- `-ns` — not-small (≈30em+)
- `-m` — medium (≈30–60em)
- `-l` — large (≈60em+)

Before using a class, confirm it exists in Ananke’s bundled build (for example search the generated `public/ananke/css/main.css` after `hugo server` or a build). Do not invent utility names from other Tachyons versions or Tailwind.

### When custom CSS is allowed

Keep overrides in [`assets/ananke/css/site.css`](assets/ananke/css/site.css), registered via `ananke.custom_css` in config. Add CSS only when Tachyons cannot express the behavior, and leave a short comment explaining why. Current exceptions:

1. Global `img { max-width: 100%; height: auto; }` so `w-100` plus HTML `width`/`height` attributes keep correct aspect ratio (do not use inline `style="height: auto"`).
2. A specificity shim so `.white` button text survives Ananke’s `.nested-links a` color rules.

### Content vs chrome

- Page body content goes through shared shells such as `layouts/_partials/site-content.html` (`mw7 center` for a readable measure).
- Wide chrome (gallery grids, full-bleed header) belongs outside that measure (for example the `after` slot on `site-content`).
- Prefer existing shortcodes (`button`, `grid`, `gallery-item`, `team-member`) over one-off HTML in content files.

## Checks before you submit

```bash
make check
```

This builds with Hugo and runs `scripts/validate_site.py` (accessibility and design invariants). Fix errors; treat warnings as guidance.

Also spot-check key pages in the browser at mobile and desktop widths (home, about, gallery list, a gallery project, and the Spanish (`/es/`) variants).
