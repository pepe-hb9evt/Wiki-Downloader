"""
download.py
===========
Download functions for PDF, Markdown, and images.
"""

import os
import re

from urllib.parse import urljoin
from bs4 import BeautifulSoup

from config import (
    session, state, counters,
    OUTPUT_PDF_DIR, OUTPUT_MD_DIR, OUTPUT_IMG_DIR,
    PDF_OPTIONS, pdf_config,
)
from helpers import safe_filename, extract_image_filename, replace_images_with_info
from mediawiki import extract_mediawiki_image_urls
from dokuwiki import extract_dokuwiki_image_urls

# Optional packages
try:
    import pdfkit
except ImportError:
    pdfkit = None

try:
    import html2text
except ImportError:
    html2text = None


# ──────────────────────────────────────────────
# CONTENT EXTRACTION
# ──────────────────────────────────────────────

def get_content_element(soup):
    """Returns the main content element from a wiki page based on wiki type."""
    if state.wiki_type == "mediawiki":
        content = soup.find("div", id="mw-content-text")
        if not content:
            content = soup.find("div", id="bodyContent")
        return content

    elif state.wiki_type == "dokuwiki":
        content = soup.select_one("div.page.group")
        if not content:
            content = soup.find("div", class_="page")
        if not content:
            content = soup.find("div", id="dokuwiki__content")
        if not content:
            content = soup.find("article")
        return content

    return None


def _get_dokuwiki_export_url(page_url: str, export_type: str = "xhtml") -> str:
    """
    Builds a DokuWiki export URL for clean content retrieval.
    DokuWiki supports ?do=export_xhtml for clean XHTML export.
    """
    if "?" in page_url:
        return f"{page_url}&do=export_{export_type}"
    else:
        return f"{page_url}?do=export_{export_type}"


# ──────────────────────────────────────────────
# PDF DOWNLOAD
# ──────────────────────────────────────────────

def download_pdf(title: str, url: str) -> None:
    """Saves a wiki page as a PDF file."""
    filename = safe_filename(title, "pdf")
    filepath = os.path.join(OUTPUT_PDF_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"   [SKIP] PDF already exists: {filename}")
        counters.pdfs_skipped += 1
        return

    try:
        kwargs = {"options": PDF_OPTIONS}
        if pdf_config:
            kwargs["configuration"] = pdf_config
        pdfkit.from_url(url, filepath, **kwargs)
        print(f"   [OK]   PDF saved: {filename}")
        counters.pdfs_saved += 1
    except Exception as e:
        print(f"   [FAIL] PDF error ({title}): {e}")
        counters.pdfs_failed += 1


# ──────────────────────────────────────────────
# MARKDOWN DOWNLOAD
# ──────────────────────────────────────────────

def download_markdown(title: str, url: str) -> None:
    """
    Saves a wiki page as a Markdown file.
    For DokuWiki, uses the ?do=export_xhtml endpoint for cleaner content.
    Images are replaced with text placeholders showing filename and dimensions.
    """
    filename = safe_filename(title, "md")
    filepath = os.path.join(OUTPUT_MD_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"   [SKIP] Markdown already exists: {filename}")
        counters.mds_skipped += 1
        return

    try:
        # For DokuWiki, use export_xhtml endpoint for cleaner content
        if state.wiki_type == "dokuwiki":
            fetch_url = _get_dokuwiki_export_url(url, "xhtml")
        else:
            fetch_url = url

        resp = session.get(fetch_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # For DokuWiki export_xhtml, the response is clean content
        if state.wiki_type == "dokuwiki":
            content = soup.find("body") or soup
        else:
            content = get_content_element(soup)

        if not content:
            raise ValueError("Could not find page content")

        # Replace <img> tags with text placeholders (filename + dimensions)
        replace_images_with_info(content)

        # Convert HTML to Markdown
        converter = html2text.HTML2Text()
        converter.ignore_links = False
        converter.ignore_images = False
        converter.body_width = 0  # No line wrapping
        converter.protect_links = True
        converter.unicode_snob = True

        markdown_text = f"# {title}\n\n" + converter.handle(str(content))

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(markdown_text)

        print(f"   [OK]   Markdown saved: {filename}")
        counters.mds_saved += 1
    except Exception as e:
        print(f"   [FAIL] Markdown error ({title}): {e}")
        counters.mds_failed += 1


# ──────────────────────────────────────────────
# IMAGE HANDLING
# ──────────────────────────────────────────────

def get_image_urls_from_page(page_url: str) -> list[str]:
    """Extracts all content image URLs from a wiki page."""
    try:
        resp = session.get(page_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"   [WARN] Page not reachable: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    content = get_content_element(soup) or soup
    image_urls = []

    for img in content.find_all("img", src=True):
        src = img["src"]
        full_url = urljoin(state.base_url, src)

        if state.wiki_type == "mediawiki":
            image_urls.extend(extract_mediawiki_image_urls(full_url))
        elif state.wiki_type == "dokuwiki":
            image_urls.extend(extract_dokuwiki_image_urls(full_url, src))

    return list(set(image_urls))  # Remove duplicates


def download_image(img_url: str) -> None:
    """Downloads an image and saves it locally."""
    filename = extract_image_filename(img_url)
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    filepath = os.path.join(OUTPUT_IMG_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"   [SKIP] Image already exists: {filename}")
        counters.imgs_skipped += 1
        return

    try:
        resp = session.get(img_url, timeout=15, stream=True)
        resp.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        print(f"   [OK]   Image saved: {filename}")
        counters.imgs_saved += 1
    except Exception as e:
        print(f"   [FAIL] Image error ({img_url}): {e}")
        counters.imgs_failed += 1
