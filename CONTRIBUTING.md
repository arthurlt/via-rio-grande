# Contributing

## Styling: Tachyons first

This Hugo site uses [Ananke v2](https://ananke-documentation.netlify.app/), which already bundles [Tachyons](https://tachyons.io/). **Layout, spacing, typography, colors, borders, and responsive variants must use Tachyons utility classes.**

Do not:

- Add a separate Tachyons (or other CSS framework) dependency
- Edit theme or Hugo module-cache CSS
- Introduce new semantic/custom CSS classes for layout or formatting that Tachyons can express

### Prefer utilities in templates

Apply classes directly in project layouts and shortcodes under `layouts/`.

### Class order (concentric)

Tachyons does not require an order, but this site follows the community
[concentric](https://rhodesmill.org/brandon/2011/concentric-css/) convention used by
[`eslint-plugin-tachyons-jsx`](https://github.com/Bebersohl/eslint-plugin-tachyons-jsx):

1. **Placement** — display, position, float, clear, flex, z-index, opacity, `center`, `dim`, …
2. **Box** — margin, padding, border, width, height, background, `list`, …
3. **Text** — font, color, alignment, decoration, `link`, line-height, measure, …
4. **Custom / non-Tachyons** — theme or project classes last (e.g. `ananke-socials`)

Within each category, sort class names **alphanumerically**. Responsive suffixes
(`-ns`, `-m`, `-l`) stay with their base class in that sort (e.g. `w-100 w-50-l w-50-m`).

Examples already used on this site (ordered):

| Purpose | Example utilities |
| --- | --- |
| Responsive column widths | `w-100 w-50-l w-50-m` |
| Spacing | `mb4 ph3 ph5-ns pv4` |
| Type scale / weight | `f3 f5 fw6 lh-copy lh-title` |
| Color | `bg-blue hover-bg-dark-blue mid-gray navy white` |
| Borders / radius | `b--black-10 ba br2 br3` |
| Flex layout | `flex flex-none flex-wrap items-center` |
| Buttons | `dib bg-blue br2 hover-bg-dark-blue ph4 pv3 f5 fw6 lh-title no-underline tc white` |
| Block button | add `db` and `w-100` in placement/box positions |
| Cards / media chrome | `b--black-10 ba` (not heavy shadows) |
| Hide/show by breakpoint | `db-l dn` |

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

- Page body content goes through shared shells such as `layouts/_partials/site-content.html` (`center mw7` for a readable measure).
- Wide chrome (gallery grids, full-bleed header) belongs outside that measure (for example the `after` slot on `site-content`).
- Prefer existing shortcodes (`button`, `grid`, `gallery-item`, `team-member`) over one-off HTML in content files.

## Checks before you submit

CI runs CSS lint, Markdown lint, Go template formatting (`gotmplfmt`), and site validation on every push/PR. Locally, the dependency-light Hugo/Python path is still:

```bash
make check
```

Optional diagnostics (same tools CI uses):

```bash
npm ci && npm run lint
go install github.com/gohugoio/gotmplfmt@v0.4.1
diff <(gotmplfmt -d layouts) <(printf '')
```

Fix errors; treat `validate_site.py` warnings as guidance.

This site has no JavaScript or JSX, so ESLint and `eslint-plugin-tachyons-jsx` are not used. Tachyons class order and naming stay a template/convention concern (this document and `scripts/validate_site.py`), not a JSX lint rule.

Also spot-check key pages in the browser at mobile and desktop widths (home, about, gallery list, a gallery project, and the Spanish (`/es/`) variants).
