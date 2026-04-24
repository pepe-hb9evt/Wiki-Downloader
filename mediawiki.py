"""
mediawiki.py
============
MediaWiki-specific functions: page listing and image URL extraction.
"""

import re

from urllib.parse import urljoin
from bs4 import BeautifulSoup

from config import session, state, MEDIAWIKI_ALL_PAGES_PATH


def get_all_page_links_mediawiki() -> list[tuple[str, str]]:
    """Reads all page links from MediaWiki's special 'All Pages' page."""
    all_pages_url = f"{state.base_url}{MEDIAWIKI_ALL_PAGES_PATH}"
    print(f"[INFO] Loading page list from: {all_pages_url}")

    resp = session.get(all_pages_url, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    pages = []

    # MediaWiki lists pages inside <ul class="mw-allpages-chunk">
    for ul in soup.select("ul.mw-allpages-chunk"):
        for a in ul.find_all("a", href=True):
            title = a.get_text(strip=True)
            url = urljoin(state.base_url, a["href"])
            pages.append((title, url))

    # Fallback: collect all links from the content area
    if not pages:
        content = soup.find("div", id="mw-content-text") or soup
        for a in content.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/index.php?title=") and "Spezial:" not in href:
                title = a.get_text(strip=True)
                url = urljoin(state.base_url, href)
                if title:
                    pages.append((title, url))

    print(f"       -> {len(pages)} pages found.\n")
    return pages


def extract_mediawiki_image_urls(full_url: str) -> list[str]:
    """Extracts original image URLs from MediaWiki image references."""
    urls = []

    if "/images/" in full_url and "thumb" not in full_url.split("/images/")[1][:10]:
        # Direct image URL (not a thumbnail)
        urls.append(full_url)
    elif "/images/thumb/" in full_url:
        # Thumbnail URL: derive the original image URL
        # e.g. /images/thumb/a/ab/Photo.jpg/300px-Photo.jpg -> /images/a/ab/Photo.jpg
        match = re.match(r"(.*/images/(?:thumb/)?./../)([^/]+\.\w+)", full_url)
        if match:
            original = f"{state.base_url}/images/{full_url.split('/images/thumb/')[1]}"
            # Remove the trailing /NNNpx-filename part
            original = re.sub(r"/\d+px-[^/]+$", "", original)
            urls.append(original)
        else:
            urls.append(full_url)

    return urls
