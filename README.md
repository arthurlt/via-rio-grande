# via-rio-grande

The website for the 501(c)(4) non-profit Via Rio Grande (Hugo + Ananke).

## Local development

```bash
hugo server
```

## Checks

Run a dependency-light build and HTML/source validation (Python stdlib + Hugo only):

```bash
make check
```

This runs `hugo --panicOnWarning` into a temporary directory, then inspects generated HTML and site-owned layouts for accessibility and design invariants. Warnings (for example oversized source images or Spanish placeholder front matter) do not fail the check; errors do.
