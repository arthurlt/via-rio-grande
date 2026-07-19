# via-rio-grande

The website for the 501(c)(4) non-profit Via Rio Grande (Hugo + Ananke).

## Local development

```bash
hugo server
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for styling conventions and the pre-submit checklist.

## Checks

GitHub Actions (`.github/workflows/checks.yml`) runs the full quality gate on every push and pull request:

1. CSS lint (`stylelint` on `assets/**/*.css`)
2. Markdown lint (`markdownlint-cli2` on docs and `content/`)
3. Go template formatting (`gotmplfmt` on `layouts/`)
4. Site validation (`scripts/validate_site.py` — Hugo build plus accessibility/design invariants)

Locally you can still run the dependency-light Hugo/Python validation alone:

```bash
make check
```

To reproduce the npm lint steps (optional; requires Node 22+):

```bash
npm ci
npm run lint
```

To check template formatting (optional; requires Go and `gotmplfmt`):

```bash
go install github.com/gohugoio/gotmplfmt@v0.4.1
diff <(gotmplfmt -d layouts) <(printf '')
```

Warnings from `validate_site.py` (for example oversized source images) do not fail the check; errors do.
