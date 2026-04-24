"""
dokuwiki.py
===========
DokuWiki-specific functions: page listing (sitemap, index, crawling)
and image URL extraction.
"""

import gzip
import time
import xml.etree.ElementTree as ET
from io import BytesIO
from urllib.parse import urljoin, urlparse, unquote, parse_qs, quote

from bs4 import BeautifulSoup

from config import session, state, DOKUWIKI_MAX_CRAWL_PAGES


# ──────────────────────────────────────────────
# PAGE LISTING: DISPATCHER
# ──────────────────────────────────────────────

def get_all_page_links_dokuwiki() -> list[tuple[str, str]]:
    """
    Gets all page links from a DokuWiki instance.
    Strategy (in order of preference):
      1. sitemap.xml / sitemap.xml.gz
      2. ?do=index page listing
      3. Recursive link crawling (last resort)
    """
    # Method 1: sitemap.xml
    pages = _try_sitemap()
    if pages:
        return pages

    # Method 2: ?do=index
    print("[INFO] Sitemap not available. Trying ?do=index page listing...")
    pages = _try_index()
    if pages:
        return pages

    # Method 3: recursive crawling (last resort)
    print("[INFO] Index not available. Falling back to recursive link crawling...")
    pages = _crawl_pages()
    if pages:
        return pages

    print("[FAIL] Could not discover any pages.")
    return []


# ──────────────────────────────────────────────
# METHOD 1: SITEMAP
# ──────────────────────────────────────────────

def _try_sitemap() -> list[tuple[str, str]]:
    """Tries to parse DokuWiki's sitemap.xml or sitemap.xml.gz to get all page URLs."""
    sitemap_urls_to_try = [
        f"{state.base_url}/sitemap.xml",
        f"{state.base_url}/sitemap.xml.gz",
    ]

    for sitemap_url in sitemap_urls_to_try:
        print(f"[INFO] Trying sitemap: {sitemap_url}")
        try:
            resp = session.get(sitemap_url, timeout=30)
            if resp.status_code != 200:
                print(f"       -> HTTP {resp.status_code}, skipping.")
                continue

            is_gzipped = sitemap_url.endswith(".gz")
            page_urls = _parse_sitemap(resp.content, is_gzipped)

            if page_urls:
                pages = [(derive_title_from_url(url), url) for url in page_urls]
                print(f"       -> {len(pages)} pages found via sitemap.\n")
                return pages
        except Exception as e:
            print(f"       -> Error: {e}")

    return []


def _parse_sitemap(content: bytes, is_gzipped: bool = False) -> list[str]:
    """
    Parses a sitemap.xml (or sitemap index) and returns all page URLs.
    Handles both regular sitemaps and sitemap index files.
    """
    if is_gzipped:
        try:
            content = gzip.GzipFile(fileobj=BytesIO(content)).read()
        except Exception:
            pass  # Try parsing as-is if decompression fails

    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return []

    # XML namespace used by sitemaps
    ns = {"sm": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = []

    # Handle sitemap index (contains references to sub-sitemaps)
    for sitemap_elem in root.findall("sm:sitemap", ns):
        loc = sitemap_elem.find("sm:loc", ns)
        if loc is not None and loc.text:
            try:
                sub_resp = session.get(loc.text.strip(), timeout=30)
                if sub_resp.status_code == 200:
                    sub_urls = _parse_sitemap(
                        sub_resp.content, loc.text.strip().endswith(".gz")
                    )
                    urls.extend(sub_urls)
            except Exception:
                pass

    # Handle regular sitemap entries
    for url_elem in root.findall("sm:url", ns):
        loc = url_elem.find("sm:loc", ns)
        if loc is not None and loc.text:
            urls.append(loc.text.strip())

    return urls


# ──────────────────────────────────────────────
# METHOD 2: ?do=index
# ──────────────────────────────────────────────

def _try_index() -> list[tuple[str, str]]:
    """
    Discovers all DokuWiki pages by using the built-in ?do=index page.
    Recursively expands all namespaces via the idx= parameter to find
    every page in the wiki.
    """
    # Determine the base index URL (handle both doku.php and URL-rewritten setups)
    index_urls_to_try = [
        f"{state.base_url}/doku.php?do=index",
        f"{state.base_url}/?do=index",
    ]

    # Find a working index URL
    working_index_url = None
    for index_url in index_urls_to_try:
        print(f"[INFO] Trying index page: {index_url}")
        try:
            resp = session.get(index_url, timeout=15)
            if resp.status_code == 200 and "idx" in resp.text.lower():
                working_index_url = index_url
                print(f"       -> Index page found.")
                break
            else:
                print(f"       -> Not a valid index page, skipping.")
        except Exception as e:
            print(f"       -> Error: {e}")

    if not working_index_url:
        return []

    # Extract the base pattern for index URLs
    if "doku.php" in working_index_url:
        index_base = working_index_url.split("?")[0]
    else:
        index_base = state.base_url + "/"

    # Recursively discover all pages via namespaces
    all_pages = []
    visited_namespaces = set()

    def explore_index_page(idx_param: str = "") -> None:
        """Loads an index page and extracts pages and sub-namespaces."""
        # Prevent processing the same namespace twice
        if idx_param in visited_namespaces:
            return
        visited_namespaces.add(idx_param)

        # Build the URL for this namespace
        if idx_param:
            url = f"{index_base}?do=index&idx={quote(idx_param, safe=':')}"
        else:
            url = working_index_url

        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                return
        except Exception:
            return

        soup = BeautifulSoup(resp.text, "html.parser")

        # Find the index list container
        index_div = (
            soup.find("div", id="index__tree")
            or soup.find("div", class_="idx")
            or soup.find("ul", class_="idx")
            or soup
        )

        # Extract all links from the index
        for a in index_div.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(state.base_url, href)
            link_text = a.get_text(strip=True)
            css_classes = " ".join(a.get("class", []))

            # Namespace links (directories to expand)
            if "idx_dir" in css_classes or ("do=index" in href and "idx=" in href):
                ns_id = _extract_namespace_from_link(href, idx_param)
                if ns_id and ns_id not in visited_namespaces:
                    explore_index_page(ns_id)

            # Page links (actual wiki pages)
            elif _is_page_link(href, css_classes):
                title = link_text if link_text else derive_title_from_url(full_url)
                if not any(p[1] == full_url for p in all_pages):
                    all_pages.append((title, full_url))

        # Progress indicator
        if all_pages and len(all_pages) % 100 == 0:
            print(f"       -> {len(all_pages)} pages discovered so far...")

        time.sleep(0.3)  # Be kind to the server

    # Start the recursive exploration from the root
    print("[INFO] Exploring index tree...")
    explore_index_page("")

    if all_pages:
        print(f"       -> {len(all_pages)} pages found via index.\n")
    else:
        print("       -> No pages found via index.")

    return all_pages


def _extract_namespace_from_link(href: str, current_namespace: str) -> str | None:
    """
    Extracts the DokuWiki namespace identifier from an index link.
    Handles both doku.php?do=index&idx=ns and URL-rewritten formats.
    """
    parsed = urlparse(href)
    qs = parse_qs(parsed.query)

    if "idx" in qs:
        return qs["idx"][0]

    return None


def _is_page_link(href: str, css_classes: str) -> bool:
    """
    Determines if an href from the DokuWiki index is an actual page link
    (not a namespace, not an action link, not an external link).
    """
    # Links with wikilink1 class are confirmed existing pages
    if "wikilink1" in css_classes:
        return True

    # Skip action links, media links, and external links
    skip_indicators = [
        "do=index", "do=edit", "do=admin", "do=login", "do=search",
        "do=media", "do=export", "do=revisions", "do=diff",
        "/_media/", "/lib/exe/", "/_detail/", "/_export/",
        "idx_dir",
    ]
    if any(indicator in href or indicator in css_classes for indicator in skip_indicators):
        return False

    # Accept links that look like DokuWiki page links
    if "doku.php?id=" in href:
        return True

    # Accept relative links within the wiki (not to external sites or special pages)
    parsed = urlparse(href)
    if not parsed.scheme and not parsed.netloc:
        if parsed.path and not parsed.path.startswith("/lib/"):
            return True

    return False


# ──────────────────────────────────────────────
# METHOD 3: RECURSIVE CRAWLING
# ──────────────────────────────────────────────

def _crawl_pages() -> list[tuple[str, str]]:
    """
    Discovers DokuWiki pages by recursively following internal links.
    Used as a last resort when neither sitemap.xml nor ?do=index is available.
    Uses two sets (visited + queued) to prevent duplicate processing
    and duplicate queue entries.
    """
    print(f"[INFO] Starting recursive crawl from: {state.base_url}")

    visited = set()         # URLs that have been fully processed
    queued = set()          # URLs that have been added to the queue (prevents duplicates)
    to_visit = [state.base_url]
    queued.add(state.base_url)
    pages = []

    while to_visit and len(visited) < DOKUWIKI_MAX_CRAWL_PAGES:
        url = to_visit.pop(0)

        # Normalize URL (remove fragment and trailing slash)
        url = url.split("#")[0].rstrip("/")
        if url in visited:
            continue
        visited.add(url)

        try:
            resp = session.get(url, timeout=15)
            if resp.status_code != 200:
                continue
        except Exception:
            continue

        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract page title from the <h1> tag or fall back to URL
        title_tag = soup.find("h1")
        if not title_tag:
            title_tag = soup.find("title")
        title = title_tag.get_text(strip=True) if title_tag else derive_title_from_url(url)

        # Only add if it looks like a real wiki content page
        if _is_content_page(url, soup):
            pages.append((title, url))
            if len(pages) % 50 == 0:
                print(f"       -> {len(pages)} pages discovered so far...")

        # Discover and queue internal links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            full_url = urljoin(url, href).split("#")[0].rstrip("/")

            # Only queue if not yet visited AND not already in the queue
            if (full_url.startswith(state.base_url)
                    and full_url not in visited
                    and full_url not in queued):
                if _is_followable_link(full_url):
                    to_visit.append(full_url)
                    queued.add(full_url)

        time.sleep(0.3)  # Be kind to the server during crawling

    print(f"       -> {len(pages)} pages found.\n")
    return pages


def _is_content_page(url: str, soup) -> bool:
    """Checks if a URL/page is a real DokuWiki content page (not admin, media, etc.)."""
    skip_patterns = [
        "do=edit", "do=admin", "do=login", "do=register", "do=profile",
        "do=revisions", "do=diff", "do=backlink", "do=index", "do=export",
        "do=media", "do=search", "do=recent", "do=sitemap",
        "/_media/", "/_detail/", "/lib/exe/", "/lib/plugins/", "/_export/",
    ]
    if any(pattern in url for pattern in skip_patterns):
        return False

    content = (
        soup.select_one("div.page.group")
        or soup.find("div", class_="page")
        or soup.find("div", id="dokuwiki__content")
        or soup.find("article")
    )
    return content is not None


def _is_followable_link(url: str) -> bool:
    """Checks if a DokuWiki URL should be followed during recursive crawling."""
    skip_patterns = [
        "do=edit", "do=admin", "do=login", "do=register", "do=profile",
        "do=revisions", "do=diff", "do=backlink", "do=export",
        "do=media", "do=search", "do=recent", "do=index",
        "/_media/", "/_detail/", "/lib/exe/", "/lib/plugins/", "/_export/",
    ]
    return not any(pattern in url for pattern in skip_patterns)


# ──────────────────────────────────────────────
# SHARED HELPERS
# ──────────────────────────────────────────────

def derive_title_from_url(url: str) -> str:
    """Derives a human-readable page title from a DokuWiki URL."""
    parsed = urlparse(url)

    # Handle doku.php?id=namespace:page format
    qs = parse_qs(parsed.query)
    if "id" in qs:
        page_id = qs["id"][0]
        return page_id.replace(":", " - ").replace("_", " ").strip()

    # Handle URL-rewritten paths like /docs/guide-user/start
    path = parsed.path.strip("/")
    if path:
        return path.replace("/", " - ").replace("_", " ").strip()

    return "Start"


def extract_dokuwiki_image_urls(full_url: str, src: str) -> list[str]:
    """Extracts image URLs from DokuWiki image references."""
    urls = []

    if "/_media/" in full_url:
        # Direct media URL: strip query parameters (e.g. cache-busting)
        clean_url = full_url.split("?")[0]
        urls.append(clean_url)

    elif "/lib/exe/fetch.php" in full_url:
        # fetch.php URL: convert to direct _media/ URL
        parsed = urlparse(full_url)
        qs = parse_qs(parsed.query)
        media = qs.get("media", [""])[0]
        if media:
            media_path = media.replace(":", "/")
            direct_url = f"{state.base_url}/_media/{media_path}"
            urls.append(direct_url)
        else:
            urls.append(full_url)

    elif "_media" in src:
        # Relative _media reference
        urls.append(full_url)

    return urls
