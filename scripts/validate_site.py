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

SOURCE_BAD_PATTERNS = (
    (re.compile(r"\bf6\s+gray\b|\bgray\s+f6\b"), "f6 gray (use f6 mid-gray for captions)"),
    (re.compile(r"\bshadow-4\b"), "shadow-4 (prefer site-card)"),
    (
        re.compile(r'style="[^"]*height:\s*auto', re.I),
        'inline height:auto (use global img { height: auto } in site.css)',
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
        LAYOUTS / "_partials" / "site-content.html": "site-prose",
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
