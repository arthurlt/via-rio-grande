#!/usr/bin/env python3
"""Dependency-light site checks for Via Rio Grande (Hugo + stdlib only)."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LAYOUTS = ROOT / "layouts"
CONTENT = ROOT / "content"
ASSETS = ROOT / "assets"
CONFIG = ROOT / "config" / "_default"
I18N = ROOT / "i18n"

SOURCE_BAD_PATTERNS = (
    (re.compile(r"\bf6\s+gray\b|\bgray\s+f6\b"), "f6 gray (use f6 mid-gray for captions)"),
    (re.compile(r"\bshadow-4\b"), "shadow-4 (prefer ba b--black-10)"),
    (
        re.compile(r'style="[^"]*height:\s*auto', re.I),
        'inline height:auto (use global img { height: auto } in site.css)',
    ),
    (
        re.compile(
            r"\b(site-prose|site-card|button-link|gallery-project-card|team-member__photo|lang-switcher)\b"
        ),
        "custom semantic class (prefer Tachyons utilities; see CONTRIBUTING.md)",
    ),
)

SITE_CSS = ASSETS / "ananke" / "css" / "site.css"
# Global responsive-image rule must keep height:auto so w-100 + width/height attrs do not skew.
IMG_HEIGHT_AUTO_RE = re.compile(
    r"(?ms)^\s*img\s*\{[^}]*\bheight:\s*auto\b",
)

EN_TOP_LEVEL = (
    CONTENT / "en" / "_index.md",
    CONTENT / "en" / "about" / "index.md",
    CONTENT / "en" / "contact.md",
    CONTENT / "en" / "letters.md",
    CONTENT / "en" / "gallery" / "_index.md",
)

ES_TOP_LEVEL = (
    CONTENT / "es" / "_index.md",
    CONTENT / "es" / "about" / "index.md",
    CONTENT / "es" / "contact.md",
    CONTENT / "es" / "letters.md",
    CONTENT / "es" / "gallery" / "_index.md",
)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
LARGE_SOURCE_BYTES = 1_000_000

# Theme/tax/alias pages where heading structure is not our responsibility
SKIP_H1_NAMES = {"404.html", "categories", "tags"}


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[int] = []
        self.ids: list[str] = []
        self.imgs: list[dict[str, str | None]] = []
        self.links: list[dict[str, str | None]] = []
        self._in_a = False
        self._a_text: list[str] = []
        self._a_attrs: dict[str, str | None] = {}
        self.is_redirect = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        ad = dict(attrs)
        if tag in {"h1", "h2", "h3", "h4", "h5", "h6"}:
            self.headings.append(int(tag[1]))
        if "id" in ad and ad["id"]:
            self.ids.append(ad["id"])
        if tag == "meta" and (ad.get("http-equiv") or "").lower() == "refresh":
            self.is_redirect = True
        if tag == "img":
            self.imgs.append(
                {
                    "alt": ad.get("alt"),
                    "width": ad.get("width"),
                    "height": ad.get("height"),
                    "src": ad.get("src"),
                }
            )
            if self._in_a and ad.get("alt"):
                self._a_text.append(ad["alt"])
        if tag == "a":
            self._in_a = True
            self._a_text = []
            self._a_attrs = {
                "href": ad.get("href"),
                "target": ad.get("target"),
                "rel": ad.get("rel"),
                "aria-label": ad.get("aria-label"),
                "title": ad.get("title"),
            }

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_a:
            text = "".join(self._a_text).strip()
            self.links.append({**self._a_attrs, "text": text})
            self._in_a = False

    def handle_data(self, data: str) -> None:
        if self._in_a:
            self._a_text.append(data)


def run_hugo(out_dir: Path) -> None:
    cmd = [
        "hugo",
        "--destination",
        str(out_dir),
        "--panicOnWarning",
        "--minify=false",
    ]
    subprocess.run(cmd, cwd=ROOT, check=True)


def check_source_patterns() -> list[str]:
    errors: list[str] = []
    for path in LAYOUTS.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        rel = path.relative_to(ROOT)
        for pattern, label in SOURCE_BAD_PATTERNS:
            if pattern.search(text):
                errors.append(f"{rel}: forbidden pattern {label}")
    return errors


def check_shared_partial() -> list[str]:
    errors: list[str] = []
    required = {
        LAYOUTS / "_partials" / "page-content.html": "site-content.html",
        LAYOUTS / "gallery" / "list.html": "site-content.html",
        LAYOUTS / "gallery" / "single.html": "site-content.html",
        LAYOUTS / "_partials" / "site-content.html": "center mw7",
    }
    for path, needle in required.items():
        if not path.exists():
            errors.append(f"missing {path.relative_to(ROOT)}")
            continue
        if needle not in path.read_text(encoding="utf-8"):
            errors.append(f"{path.relative_to(ROOT)}: expected to reference {needle}")
    return errors


def check_responsive_img_css() -> list[str]:
    """Require global img { height: auto } so aspect ratios are not skewed."""
    if not SITE_CSS.exists():
        return [f"missing {SITE_CSS.relative_to(ROOT)}"]
    text = SITE_CSS.read_text(encoding="utf-8")
    if not IMG_HEIGHT_AUTO_RE.search(text):
        return [
            f"{SITE_CSS.relative_to(ROOT)}: missing global "
            "img { height: auto } rule (required for responsive images)"
        ]
    return []


def front_matter_fields(path: Path) -> dict[str, str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("+++"):
        return {}
    end = text.find("+++", 3)
    if end < 0:
        return {}
    block = text[3:end]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        fields[key.strip()] = val.strip().strip("\"'")
    return fields


def check_front_matter() -> list[str]:
    warnings: list[str] = []
    for path in EN_TOP_LEVEL:
        if not path.exists():
            warnings.append(f"missing expected EN page {path.relative_to(ROOT)}")
            continue
        fields = front_matter_fields(path)
        for key in ("description", "images"):
            if key not in fields or not fields[key]:
                warnings.append(f"{path.relative_to(ROOT)}: missing front matter {key}")
    for path in ES_TOP_LEVEL:
        if not path.exists():
            warnings.append(f"missing expected ES page {path.relative_to(ROOT)}")
            continue
        fields = front_matter_fields(path)
        for key in ("description", "images"):
            if key not in fields or not fields[key]:
                warnings.append(f"{path.relative_to(ROOT)}: missing front matter {key}")
    return warnings


def content_md_relpaths(lang: str) -> set[str]:
    base = CONTENT / lang
    if not base.is_dir():
        return set()
    return {p.relative_to(base).as_posix() for p in base.rglob("*.md") if p.is_file()}


def gallery_srcs(path: Path) -> list[str]:
    if not path.exists():
        return []
    return re.findall(r'^src = "([^"]+)"', path.read_text(encoding="utf-8"), re.M)


def toml_section_keys(path: Path) -> set[str]:
    """Top-level [section] keys from a simple TOML i18n/menu-style file."""
    if not path.exists():
        return set()
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line.startswith("[") and line.endswith("]") and not line.startswith("[["):
            keys.add(line[1:-1].strip())
    return keys


def menu_entries(path: Path) -> list[tuple[str, str, str]]:
    """Return (pageRef_or_url, weight, kind) for each uncommented [[main]] entry."""
    if not path.exists():
        return []
    entries: list[tuple[str, str, str]] = []
    page_ref = ""
    url = ""
    weight = ""
    in_main = False
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        if line == "[[main]]":
            if in_main and (page_ref or url):
                kind = "pageRef" if page_ref else "url"
                entries.append((page_ref or url, weight, kind))
            in_main = True
            page_ref = ""
            url = ""
            weight = ""
            continue
        if not in_main:
            continue
        if line.startswith("pageRef"):
            page_ref = line.partition("=")[2].strip().strip("\"'")
        elif line.startswith("url"):
            url = line.partition("=")[2].strip().strip("\"'")
        elif line.startswith("weight"):
            weight = line.partition("=")[2].strip()
    if in_main and (page_ref or url):
        kind = "pageRef" if page_ref else "url"
        entries.append((page_ref or url, weight, kind))
    return entries


def check_content_parity() -> list[str]:
    """Require the same markdown page inventory in en and es."""
    errors: list[str] = []
    en_pages = content_md_relpaths("en")
    es_pages = content_md_relpaths("es")
    for rel in sorted(en_pages - es_pages):
        errors.append(f"missing Spanish content page: content/es/{rel}")
    for rel in sorted(es_pages - en_pages):
        errors.append(f"extra Spanish content page without English twin: content/es/{rel}")
    return errors


def check_gallery_parity() -> list[str]:
    """Require matching UVU project bundles and image src lists across languages."""
    errors: list[str] = []
    en_gallery = CONTENT / "en" / "gallery"
    es_gallery = CONTENT / "es" / "gallery"
    en_projects = {
        p.name
        for p in en_gallery.glob("project-*")
        if p.is_dir() and (p / "index.md").exists()
    }
    es_projects = {
        p.name
        for p in es_gallery.glob("project-*")
        if p.is_dir() and (p / "index.md").exists()
    }
    for name in sorted(en_projects - es_projects):
        errors.append(f"missing Spanish gallery project: content/es/gallery/{name}/index.md")
    for name in sorted(es_projects - en_projects):
        errors.append(
            f"extra Spanish gallery project without English twin: "
            f"content/es/gallery/{name}/index.md"
        )
    for name in sorted(en_projects & es_projects):
        en_path = en_gallery / name / "index.md"
        es_path = es_gallery / name / "index.md"
        en_src = gallery_srcs(en_path)
        es_src = gallery_srcs(es_path)
        if en_src != es_src:
            errors.append(
                f"gallery image src mismatch for {name}: "
                f"en={en_src} es={es_src}"
            )
        en_fields = front_matter_fields(en_path)
        es_fields = front_matter_fields(es_path)
        if en_fields.get("weight") != es_fields.get("weight"):
            errors.append(
                f"gallery weight mismatch for {name}: "
                f"en={en_fields.get('weight')!r} es={es_fields.get('weight')!r}"
            )
        for key in ("description",):
            if key not in es_fields or not es_fields[key]:
                errors.append(f"{es_path.relative_to(ROOT)}: missing front matter {key}")
    return errors


def check_i18n_parity() -> list[str]:
    errors: list[str] = []
    en_keys = toml_section_keys(I18N / "en.toml")
    es_keys = toml_section_keys(I18N / "es.toml")
    for key in sorted(en_keys - es_keys):
        errors.append(f"missing i18n key in es.toml: [{key}]")
    for key in sorted(es_keys - en_keys):
        errors.append(f"extra i18n key in es.toml without English twin: [{key}]")
    return errors


def check_menu_parity() -> list[str]:
    """Menus must share the same pageRef/url + weight structure (names may differ)."""
    errors: list[str] = []
    en_menu = menu_entries(CONFIG / "menus.en.toml")
    es_menu = menu_entries(CONFIG / "menus.es.toml")
    if len(en_menu) != len(es_menu):
        errors.append(
            f"menu entry count mismatch: en={len(en_menu)} es={len(es_menu)}"
        )
    for idx, (en_entry, es_entry) in enumerate(zip(en_menu, es_menu)):
        if en_entry != es_entry:
            errors.append(
                f"menu structure mismatch at index {idx}: "
                f"en={en_entry} es={es_entry}"
            )
    # If lengths differ, also flag trailing unmatched entries.
    if len(en_menu) > len(es_menu):
        for entry in en_menu[len(es_menu) :]:
            errors.append(f"missing Spanish menu entry for {entry}")
    elif len(es_menu) > len(en_menu):
        for entry in es_menu[len(en_menu) :]:
            errors.append(f"extra Spanish menu entry without English twin: {entry}")
    return errors


def check_large_sources() -> list[str]:
    warnings: list[str] = []
    for base in (CONTENT, ASSETS):
        if not base.exists():
            continue
        for path in base.rglob("*"):
            if path.suffix.lower() not in IMAGE_EXTS or not path.is_file():
                continue
            size = path.stat().st_size
            if size > LARGE_SOURCE_BYTES:
                mb = size / 1_000_000
                warnings.append(
                    f"{path.relative_to(ROOT)}: source image {mb:.1f}MB (>1MB); "
                    "consider optimizing before commit"
                )
    return warnings


def should_skip_h1(rel: Path) -> bool:
    parts = rel.parts
    if rel.name in SKIP_H1_NAMES:
        return True
    if "categories" in parts or "tags" in parts:
        return True
    return False


def is_project_content_image(src: str) -> bool:
    """Images our layouts are responsible for sizing."""
    if not src:
        return False
    # Hugo processed resources and site content galleries/portraits
    markers = (
        "/gallery/",
        "project-",
        "/about/",
        "/images/",
    )
    if any(m in src for m in markers):
        # Logo is decorative chrome with explicit width/height in our nav override
        if "logo" in src or "favicon" in src:
            return False
        return True
    return False


def check_html(public: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    for path in sorted(public.rglob("*.html")):
        rel = path.relative_to(public)
        text = path.read_text(encoding="utf-8", errors="replace")
        parser = PageParser()
        parser.feed(text)
        if parser.is_redirect or 'http-equiv="refresh"' in text.lower():
            continue

        seen: dict[str, int] = defaultdict(int)
        for i in parser.ids:
            seen[i] += 1
        for i, count in seen.items():
            if count > 1:
                errors.append(f"{rel}: duplicate id {i!r} ({count}x)")

        if not should_skip_h1(rel):
            h1s = sum(1 for h in parser.headings if h == 1)
            if h1s != 1:
                errors.append(f"{rel}: expected exactly one h1, found {h1s}")

            last = 0
            for level in parser.headings:
                if last and level > last + 1:
                    errors.append(f"{rel}: heading skips from h{last} to h{level}")
                last = level

        for img in parser.imgs:
            src = img.get("src") or ""
            if img.get("alt") is None:
                errors.append(f"{rel}: img missing alt attribute (src={src!r})")
            if is_project_content_image(src) and (
                not img.get("width") or not img.get("height")
            ):
                errors.append(f"{rel}: img missing width/height (src={src!r})")

        for link in parser.links:
            target = (link.get("target") or "").lower()
            rel_attr = (link.get("rel") or "").lower()
            href = link.get("href") or ""
            if target == "_blank":
                if "noopener" not in rel_attr or "noreferrer" not in rel_attr:
                    errors.append(
                        f"{rel}: target=_blank without rel noopener noreferrer "
                        f"(href={href!r})"
                    )
            text_label = (link.get("text") or "").strip()
            aria = (link.get("aria-label") or "").strip()
            title = (link.get("title") or "").strip()
            if not text_label and not aria and not title and href and not href.startswith("#"):
                warnings.append(
                    f"{rel}: link with empty accessible name (href={href!r})"
                )

    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--public",
        type=Path,
        help="Use an existing public/ directory instead of building to a temp dir",
    )
    args = parser.parse_args()

    errors: list[str] = []
    warnings: list[str] = []

    errors.extend(check_source_patterns())
    errors.extend(check_shared_partial())
    errors.extend(check_responsive_img_css())
    errors.extend(check_content_parity())
    errors.extend(check_gallery_parity())
    errors.extend(check_i18n_parity())
    errors.extend(check_menu_parity())
    warnings.extend(check_front_matter())
    warnings.extend(check_large_sources())

    if args.public:
        public = args.public
        if not public.is_dir():
            print(f"ERROR: --public {public} is not a directory", file=sys.stderr)
            return 2
        html_err, html_warn = check_html(public)
        errors.extend(html_err)
        warnings.extend(html_warn)
    else:
        with tempfile.TemporaryDirectory(prefix="vrg-hugo-") as tmp:
            public = Path(tmp) / "public"
            try:
                run_hugo(public)
            except subprocess.CalledProcessError as exc:
                print(f"ERROR: hugo failed with exit {exc.returncode}", file=sys.stderr)
                return 1
            html_err, html_warn = check_html(public)
            errors.extend(html_err)
            warnings.extend(html_warn)

    for w in warnings:
        print(f"WARN: {w}")
    for e in errors:
        print(f"ERROR: {e}")

    print(
        f"validate_site: {len(errors)} error(s), {len(warnings)} warning(s)",
        file=sys.stderr,
    )
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
