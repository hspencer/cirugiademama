#!/usr/bin/env python3
"""
WordPress WXR → Jekyll migrator for cirugiademama.cl

What it does:
  - Parses the WordPress export XML (WXR 1.2)
  - Extracts pages, glossary terms, and image attachments
  - Converts post HTML to Markdown (kramdown-flavoured)
  - Downloads attached images into assets/images/
  - Maps each page to its top-level navigation section by slug
  - Wraps glossary surface forms in <button class="glossary-term"> in body text
  - Writes drafts to _drafts/ for the curator to review and promote

Output:
  _drafts/<slug>.md       - candidate _pages/ entries (status: scraped)
  _glossary/<slug>.md     - glossary collection entries
  assets/images/<file>    - downloaded attachments

Curation flow:
  1. Run this script once.
  2. Open each draft, edit if needed, then move to _pages/<slug>.md.
  3. Glossary terms are usable as soon as they live under _glossary/.

Dependencies:
  pip install requests markdownify beautifulsoup4 lxml
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable
from urllib.parse import urlparse

try:
    import requests
    from markdownify import markdownify as md
    from bs4 import BeautifulSoup
except ImportError as e:
    print(
        "Missing dependency: " + str(e) + "\n"
        "Install with: pip install requests markdownify beautifulsoup4 lxml",
        file=sys.stderr,
    )
    sys.exit(1)

NS = {
    "wp":      "http://wordpress.org/export/1.2/",
    "content": "http://purl.org/rss/1.0/modules/content/",
    "excerpt": "http://wordpress.org/export/1.2/excerpt/",
    "dc":      "http://purl.org/dc/elements/1.1/",
}

# Map page slug → (section_key, section_title) — derived from the legacy menu.
SECTION_MAP: dict[str, tuple[str, str]] = {
    # El cáncer
    "que-es-el-cancer":         ("el-cancer", "El cáncer"),
    "mi-riesgo":                ("el-cancer", "El cáncer"),
    "etapas-del-cancer":        ("el-cancer", "El cáncer"),
    "cancer-de-mama-en-hombres": ("el-cancer", "El cáncer"),
    "sintomas":                 ("el-cancer", "El cáncer"),

    # Detección
    "autoexamen-mamario":             ("deteccion", "Detección"),
    "examen-fisico-por-especialista": ("deteccion", "Detección"),
    "mamografia":                     ("deteccion", "Detección"),
    "mamografia-3d":                  ("deteccion", "Detección"),
    "ecografia":                      ("deteccion", "Detección"),
    "resonancia-magnetica":           ("deteccion", "Detección"),
    "biopsia":                        ("deteccion", "Detección"),

    # Tipos
    "cancer-in-situ":     ("tipos", "Tipos"),
    "cancer-invasor":     ("tipos", "Tipos"),
    "cancer-inflamatorio": ("tipos", "Tipos"),
    "enfermedad-de-paget": ("tipos", "Tipos"),
    "tipos-especiales":   ("tipos", "Tipos"),

    # Tratamiento
    "cirugia":         ("tratamiento", "Tratamiento"),
    "radioterapia":    ("tratamiento", "Tratamiento"),
    "quimioterapia":   ("tratamiento", "Tratamiento"),
    "terapia-hormonal": ("tratamiento", "Tratamiento"),
    "herceptina":      ("tratamiento", "Tratamiento"),

    # Post cáncer
    "recurrencia":             ("post-cancer", "Post cáncer"),
    "linfedema":               ("post-cancer", "Post cáncer"),
    "fertilidad-y-sexualidad": ("post-cancer", "Post cáncer"),
    "alimentacion-y-ejercicio": ("post-cancer", "Post cáncer"),

    # Enfermedades benignas
    "tumores-benignos": ("enfermedades-benignas", "Enfermedades Benignas"),
    "ginecomastia":     ("enfermedades-benignas", "Enfermedades Benignas"),
}

# Pages that should NOT be migrated as content pages (handled differently or dropped).
SKIP_SLUGS = {
    "cirugiademamacl",          # the original homepage; we have our own index.html
    "noticias",                 # blog index, dropped per user decision
    "glosario",                 # we have our own glosario.html that lists the collection
    "preguntas-y-respuestas",   # rebuild as a structured FAQPage by hand
}


@dataclass
class WordPressItem:
    post_id: int
    title: str
    slug: str
    link: str
    post_type: str
    status: str
    content_html: str
    excerpt: str
    pub_date: str
    attachment_url: str | None = None
    parent_id: int = 0


@dataclass
class GlossaryEntry:
    slug: str
    term: str
    aliases: list[str] = field(default_factory=list)
    definition_html: str = ""

    @property
    def definition_md(self) -> str:
        return html_to_markdown(self.definition_html).strip()


def text_of(elem: ET.Element | None, default: str = "") -> str:
    if elem is None or elem.text is None:
        return default
    return elem.text


def parse_items(xml_path: Path) -> list[WordPressItem]:
    tree = ET.parse(xml_path)
    root = tree.getroot()
    channel = root.find("channel")
    if channel is None:
        raise RuntimeError("No <channel> in WXR export")

    items: list[WordPressItem] = []
    for it in channel.findall("item"):
        items.append(WordPressItem(
            post_id      = int(text_of(it.find("wp:post_id", NS), "0")),
            title        = text_of(it.find("title")),
            slug         = text_of(it.find("wp:post_name", NS)),
            link         = text_of(it.find("link")),
            post_type    = text_of(it.find("wp:post_type", NS)),
            status       = text_of(it.find("wp:status", NS)),
            content_html = text_of(it.find("content:encoded", NS)),
            excerpt      = text_of(it.find("excerpt:encoded", NS)),
            pub_date     = text_of(it.find("pubDate")),
            attachment_url = text_of(it.find("wp:attachment_url", NS)) or None,
            parent_id    = int(text_of(it.find("wp:post_parent", NS), "0")),
        ))
    return items


def html_to_markdown(content_html: str) -> str:
    if not content_html:
        return ""
    # Strip Gutenberg block comments (e.g. <!-- wp:paragraph --> ... <!-- /wp:paragraph -->).
    content_html = re.sub(r"<!--\s*/?wp:[^>]+-->", "", content_html)
    # Strip a few common WordPress shortcodes that markdownify won't handle.
    content_html = re.sub(r"\[/?(?:caption|gallery|embed|vc_[^\]]+)[^\]]*\]", "", content_html)

    # Run through markdownify
    text = md(content_html, heading_style="ATX", bullets="-", strip=["script", "style", "a"])
    # markdownify with strip=["a"] removes anchor wrappers around images
    # (WordPress emits <a href="full"><img src="thumb"></a>), but it also
    # strips real links — re-run on original HTML keeping anchors, then
    # post-process to remove only image-wrapping anchors.
    text = md(content_html, heading_style="ATX", bullets="-", strip=["script", "style"])
    # Remove <a>...<img>...</a> wrappers (kept as `[![alt](thumb)](full)` by markdownify).
    text = re.sub(r"\[(\!\[[^\]]*\]\([^\)]+\))\]\([^\)]+\)", r"\1", text)
    # Tag every image with the in-text float class so curators don't have to.
    text = re.sub(r"(\!\[[^\]]*\]\([^\)]+\))(?!\{)", r"\1{:.img-in-text}", text)
    # Drop empty image syntax produced by malformed source markup.
    text = re.sub(r"\!\[\]\(\)\{:\.img-in-text\}", "", text)
    text = re.sub(r"\!\[\]\(\)", "", text)
    # Collapse 3+ newlines.
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip() + "\n"


def slugify(value: str) -> str:
    """Lowercase, collapse whitespace, strip diacritics minimally."""
    import unicodedata
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    value = re.sub(r"[^a-zA-Z0-9]+", "-", value).strip("-").lower()
    return value or "term"


def yaml_quote(value: str) -> str:
    """Always quote with double quotes; escape inner quotes and backslashes."""
    if value is None:
        return '""'
    s = str(value).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{s}"'


def yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(yaml_quote(v) for v in values) + "]"


def write_front_matter(fields: dict) -> str:
    lines = ["---"]
    for k, v in fields.items():
        if v is None:
            continue
        if isinstance(v, list):
            lines.append(f"{k}: {yaml_list(v)}")
        elif isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif isinstance(v, (int, float)):
            lines.append(f"{k}: {v}")
        else:
            lines.append(f"{k}: {yaml_quote(v)}")
    lines.append("---")
    return "\n".join(lines)


def section_for(slug: str) -> tuple[str | None, str | None]:
    if slug in SECTION_MAP:
        return SECTION_MAP[slug]
    return (None, None)


# ---------- Glossary handling ----------

def build_glossary(items: list[WordPressItem]) -> list[GlossaryEntry]:
    glossary: list[GlossaryEntry] = []
    for it in items:
        if it.post_type != "glossary" or it.status != "publish":
            continue
        term = html.unescape(it.title.strip())
        slug = it.slug or slugify(term)
        aliases = [term]
        # Common Spanish variants: simple plural forms
        if not term.endswith("s"):
            aliases.append(term + "s")
        glossary.append(GlossaryEntry(
            slug=slug,
            term=term,
            aliases=aliases,
            definition_html=it.content_html,
        ))
    glossary.sort(key=lambda g: g.term.lower())
    return glossary


def annotate_glossary_terms(markdown_body: str, glossary: list[GlossaryEntry]) -> str:
    """
    Wrap occurrences of any glossary surface form in:
        <button class="glossary-term" data-term-slug="slug">term</button>

    Only wraps whole-word matches outside existing markdown links/code/headings.
    """
    if not glossary or not markdown_body:
        return markdown_body

    # Build a regex that matches any alias as a whole word, longest first to avoid
    # partial overlaps (e.g. "ganglio centinela" before "ganglio").
    by_alias: dict[str, GlossaryEntry] = {}
    for entry in glossary:
        for alias in entry.aliases:
            by_alias.setdefault(alias.lower(), entry)
    aliases_sorted = sorted(by_alias.keys(), key=len, reverse=True)
    pattern = re.compile(
        r"(?<![\w-])(" + "|".join(re.escape(a) for a in aliases_sorted) + r")(?![\w-])",
        flags=re.IGNORECASE,
    )

    # Split the body into markdown-aware segments so we don't rewrite code, links or headings.
    out_parts: list[str] = []
    skip_block = False
    for line in markdown_body.splitlines(keepends=True):
        stripped = line.strip()
        if stripped.startswith("```"):
            skip_block = not skip_block
            out_parts.append(line)
            continue
        if skip_block or stripped.startswith("#") or stripped.startswith("|"):
            out_parts.append(line)
            continue
        # Skip lines that are pure links or images
        if re.match(r"^\s*!?\[.*\]\(.*\)\s*$", line):
            out_parts.append(line)
            continue

        annotated = annotate_one_line(line, pattern, by_alias)
        out_parts.append(annotated)

    return "".join(out_parts)


def annotate_one_line(line: str, pattern: re.Pattern, by_alias: dict[str, GlossaryEntry]) -> str:
    seen: set[str] = set()  # only annotate first occurrence per line per slug

    def replace(match: re.Match) -> str:
        text = match.group(1)
        entry = by_alias.get(text.lower())
        if entry is None or entry.slug in seen:
            return text
        seen.add(entry.slug)
        return (
            f'<button class="glossary-term" type="button" '
            f'data-term-slug="{entry.slug}" '
            f'aria-describedby="glossary-popover-{entry.slug}">{text}</button>'
        )

    # Only annotate text outside markdown link constructs `[text](href)`.
    parts = re.split(r"(\[[^\]]+\]\([^)]+\)|`[^`]+`)", line)
    return "".join(
        part if (part.startswith("[") or part.startswith("`")) else pattern.sub(replace, part)
        for part in parts
    )


# ---------- Image handling ----------

def download_image(url: str, dest_dir: Path, dry_run: bool = False) -> str | None:
    """Download an image; return the local path relative to repo root."""
    parsed = urlparse(url)
    name = os.path.basename(parsed.path) or "image"
    dest = dest_dir / name
    rel = "/" + str(dest.relative_to(dest_dir.parent.parent)).replace("\\", "/")

    if dest.exists():
        return rel
    if dry_run:
        print(f"  [dry-run] would download {url} -> {dest}")
        return rel

    try:
        r = requests.get(url, timeout=30)
        r.raise_for_status()
    except Exception as e:
        print(f"  ! failed to fetch {url}: {e}", file=sys.stderr)
        return None

    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(r.content)
    print(f"  ✓ saved {rel}")
    return rel


def rewrite_image_urls(markdown_body: str, downloads: dict[str, str]) -> str:
    for source_url, local_path in downloads.items():
        markdown_body = markdown_body.replace(source_url, local_path)
        # WordPress sometimes serves http/https variants.
        if source_url.startswith("https://"):
            markdown_body = markdown_body.replace("http://" + source_url[8:], local_path)
    return markdown_body


# ---------- Output ----------

def write_page_draft(
    item: WordPressItem,
    glossary: list[GlossaryEntry],
    image_downloads: dict[str, str],
    pages_dir: Path,
) -> None:
    section_key, section_title = section_for(item.slug)
    body_md = html_to_markdown(item.content_html)
    body_md = rewrite_image_urls(body_md, image_downloads)
    body_md = annotate_glossary_terms(body_md, glossary)

    front = {
        "title":          item.title,
        "slug":           item.slug,
        "permalink":      f"/{item.slug}/",
        "section":        section_title,
        "section_key":    section_key,
        "section_url":    f"/{section_key}/" if section_key else None,
        "description":    "",        # to be filled by curator (≤160 chars)
        "lead":           "",        # optional intro paragraph
        "schema_type":    "MedicalWebPage",
        "legacy_url":     item.link,
        "legacy_post_id": item.post_id,
        "status":         "scraped",  # change to "published" when promoted
    }

    pages_dir.mkdir(parents=True, exist_ok=True)
    out_path = pages_dir / f"{item.slug}.md"
    out_path.write_text(write_front_matter(front) + "\n\n" + body_md, encoding="utf-8")
    print(f"  → page: {out_path}")


def write_glossary_entry(entry: GlossaryEntry, glossary_dir: Path) -> None:
    front = {
        "term":    entry.term,
        "slug":    entry.slug,
        "aliases": entry.aliases,
    }
    glossary_dir.mkdir(parents=True, exist_ok=True)
    out_path = glossary_dir / f"{entry.slug}.md"
    out_path.write_text(write_front_matter(front) + "\n\n" + entry.definition_md, encoding="utf-8")


# ---------- Main ----------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("xml", type=Path, help="path to the WordPress WXR XML export")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent,
                        help="repository root (default: parent of scripts/)")
    parser.add_argument("--no-images", action="store_true", help="skip image downloads")
    parser.add_argument("--dry-run", action="store_true", help="don't write files")
    args = parser.parse_args()

    if not args.xml.exists():
        print(f"XML file not found: {args.xml}", file=sys.stderr)
        return 1

    pages_dir    = args.root / "_pages"
    glossary_dir = args.root / "_glossary"
    images_dir   = args.root / "assets" / "images"
    if not args.dry_run:
        pages_dir.mkdir(parents=True, exist_ok=True)
        glossary_dir.mkdir(parents=True, exist_ok=True)
        images_dir.mkdir(parents=True, exist_ok=True)

    print(f"Parsing {args.xml} …")
    items = parse_items(args.xml)
    print(f"  found {len(items)} items")

    glossary = build_glossary(items)
    print(f"\nGlossary: {len(glossary)} entries")
    if not args.dry_run:
        for entry in glossary:
            write_glossary_entry(entry, glossary_dir)
        print(f"  wrote {len(glossary)} files to {glossary_dir}")

    # Images
    image_downloads: dict[str, str] = {}
    image_items = [it for it in items if it.post_type == "attachment" and it.attachment_url]
    print(f"\nImages: {len(image_items)} attachments")
    for it in image_items:
        if args.no_images:
            continue
        local = download_image(it.attachment_url, images_dir, dry_run=args.dry_run)
        if local:
            image_downloads[it.attachment_url] = local

    # Pages
    pages = [
        it for it in items
        if it.post_type == "page"
        and it.status == "publish"
        and it.slug not in SKIP_SLUGS
    ]
    print(f"\nPages: {len(pages)} pages to write")
    if not args.dry_run:
        for item in pages:
            write_page_draft(item, glossary, image_downloads, pages_dir)

    print("\nDone.")
    print("Next steps:")
    print("  1. Review files in _pages/ and edit metadata (description, lead).")
    print("  2. Run: bundle exec jekyll serve")
    print("  3. Pages with status: scraped are still served — change to")
    print("     'published' once curated, or set 'sitemap: false' to hide.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
