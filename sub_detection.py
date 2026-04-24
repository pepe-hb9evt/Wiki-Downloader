"""
detection.py
============
Auto-detection of the wiki engine type (MediaWiki or DokuWiki).
"""

from bs4 import BeautifulSoup

from sub_config import session
from sub_helpers import print_n_log


def detect_wiki_type(base_url: str) -> str | None:
    """
    Tries to auto-detect whether the wiki at base_url is MediaWiki or DokuWiki.
    Checks the meta generator tag, URL patterns of internal links,
    and known HTML signatures.
    Returns "mediawiki", "dokuwiki", or None if detection fails.
    """
    print_n_log(f"[INFO] Auto-detecting wiki type for: {base_url}")

    try:
        resp = session.get(base_url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        html_lower = resp.text.lower()

        # --- Check 1: Meta generator tag (most reliable single indicator) ---
        generator = soup.find("meta", attrs={"name": "generator"})
        if generator and generator.get("content"):
            gen_content = generator["content"].lower()
            if "mediawiki" in gen_content:
                print_n_log("[INFO] Detected: MediaWiki (via meta generator tag)")
                return "mediawiki"
            if "dokuwiki" in gen_content:
                print_n_log("[INFO] Detected: DokuWiki (via meta generator tag)")
                return "dokuwiki"

        # --- Check 2: URL patterns of internal links ---
        all_links = [a.get("href", "") for a in soup.find_all("a", href=True)]

        mediawiki_url_count = sum(
            1 for href in all_links
            if "/index.php?title=" in href or "/wiki/" in href
        )
        dokuwiki_url_count = sum(
            1 for href in all_links
            if "/doku.php?id=" in href or "/lib/exe/" in href
        )

        if mediawiki_url_count > dokuwiki_url_count and mediawiki_url_count >= 3:
            print_n_log(f"[INFO] Detected: MediaWiki (via URL patterns: {mediawiki_url_count} matches)")
            return "mediawiki"
        if dokuwiki_url_count > mediawiki_url_count and dokuwiki_url_count >= 3:
            print_n_log(f"[INFO] Detected: DokuWiki (via URL patterns: {dokuwiki_url_count} matches)")
            return "dokuwiki"

        # --- Check 3: HTML structure indicators (fallback) ---
        mediawiki_hints = [
            "mw-content-text", "mw-navigation", "mw-wiki-logo",
        ]
        if any(hint in html_lower for hint in mediawiki_hints):
            print_n_log("[INFO] Detected: MediaWiki (via HTML structure)")
            return "mediawiki"

        dokuwiki_hints = [
            "dokuwiki__content", "dw__toc", "wiki__text",
        ]
        if any(hint in html_lower for hint in dokuwiki_hints):
            print_n_log("[INFO] Detected: DokuWiki (via HTML structure)")
            return "dokuwiki"

        # --- Check 4: MediaWiki API endpoint (last resort) ---
        try:
            api_url = f"{base_url}/api.php?action=query&meta=siteinfo&format=json"
            api_resp = session.get(api_url, timeout=5)
            if api_resp.status_code == 200 and "mediawiki" in api_resp.text.lower():
                print_n_log("[INFO] Detected: MediaWiki (via API endpoint)")
                return "mediawiki"
        except Exception:
            pass

    except Exception as e:
        print_n_log(f"[WARN] Auto-detection failed: {e}")

    return None
