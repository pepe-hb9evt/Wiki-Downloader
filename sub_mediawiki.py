"""
sub_mediawiki.py
============
MediaWiki-specific functions: page listing and image URL extraction.
"""

import re

from urllib.parse import urljoin
from bs4 import BeautifulSoup

from sub_config import session, state, ALL_PAGES_PATH_1, ALL_PAGES_PATH_2
from sub_helpers import print_n_log


def get_all_page_links_mediawiki() -> list[tuple[str, str]]:
    """
    Reads all page links from MediaWiki's special 'All Pages' page.
    Tries ALL_PAGES_PATH_1 (German) first, then ALL_PAGES_PATH_2 (English).
    """
    paths_to_try = [
        (ALL_PAGES_PATH_1, "path 1"),
        (ALL_PAGES_PATH_2, "path 2"),
    ]

    for path, label in paths_to_try:
        all_pages_url = f"{state.base_url}{path}"
        print_n_log(f"[INFO] Trying {label}: {all_pages_url}")

        try:
            resp = session.get(all_pages_url, timeout=15)
            if resp.status_code != 200:
                print_n_log(f"       -> HTTP {resp.status_code}, skipping.")
                continue
        except Exception as e:
            print_n_log(f"       -> Error: {e}")
            continue

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
                if href.startswith("/index.php?title=") and "Spezial:" not in href and "Special:" not in href:
                    title = a.get_text(strip=True)
                    url = urljoin(state.base_url, href)
                    if title:
                        pages.append((title, url))

        if pages:
            print_n_log(f"       -> {len(pages)} pages found.\n")
            return pages
        else:
            print_n_log(f"       -> No pages found, trying next path...")

    print_n_log("[FAIL] Could not find any pages via either path.\n")
    return []


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
