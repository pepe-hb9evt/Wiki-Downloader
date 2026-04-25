"""
helpers.py
==========
General-purpose helper functions used across multiple modules.
Provides the central print_n_log() function that writes to both terminal and log file.
"""

import os
import re
import sys
from datetime import datetime
from struct import unpack
from urllib.parse import urljoin, urlparse, unquote, parse_qs

import requests
from bs4 import BeautifulSoup

from sub_config import session, state, LOG_FILE


# ──────────────────────────────────────────────
# LOGGING
# ──────────────────────────────────────────────

def print_n_log(message: str = "") -> None:
    """
    Prints a message to the terminal and appends it to the log file.
    The log file is never overwritten, new entries are always appended.
    """
    print(message)
    try:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(message + "\n")
    except Exception:
        pass  # Never let logging errors break the program


def log_session_header() -> None:
    """Writes a session separator and timestamp to the log file."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    separator = "\n" + "=" * 55
    header = f"  Session started: {timestamp}"
    print_n_log(separator)
    print_n_log(header)
    print_n_log("=" * 55)


# ──────────────────────────────────────────────
# PROGRAM CONTROL
# ──────────────────────────────────────────────

def abort_program():
    """Exits the program gracefully after user chose to cancel."""
    print_n_log("\n[INFO] Cancelled by user. Goodbye!")
    sys.exit(0)


# ──────────────────────────────────────────────
# URL VALIDATION
# ──────────────────────────────────────────────

def validate_url(url: str) -> tuple[bool, str]:
    """
    Validates that the given URL is reachable and returns an HTML page
    that is not an HTTP error response.
    Returns (is_valid, message).
    """
    # Check basic URL format
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False, "Invalid URL format. Please include http:// or https://"

    try:
        resp = session.get(url, timeout=15, allow_redirects=True)
    except requests.exceptions.ConnectionError:
        return False, f"Connection failed. Could not reach {parsed.netloc}"
    except requests.exceptions.Timeout:
        return False, "Connection timed out after 15 seconds."
    except requests.exceptions.TooManyRedirects:
        return False, "Too many redirects."
    except requests.exceptions.RequestException as e:
        return False, f"Request error: {e}"

    # Check HTTP status code
    if resp.status_code >= 400:
        return False, f"HTTP error {resp.status_code} ({resp.reason})"

    # Check that the response contains HTML content
    content_type = resp.headers.get("Content-Type", "").lower()
    if "text/html" not in content_type and "application/xhtml" not in content_type:
        return False, f"Not an HTML page (Content-Type: {content_type})"

    # Check that the HTML body is not essentially empty
    if len(resp.text.strip()) < 100:
        return False, "Page appears to be empty or too short."

    # Check for common soft-error indicators in the HTML content
    # (some servers return 200 OK but display an error page)
    html_lower = resp.text.lower()
    soft_error_patterns = [
        "<title>404", "<title>403", "<title>500",
        "<title>502", "<title>503",
        "page not found", "404 not found", "403 forbidden",
        "500 internal server error", "502 bad gateway",
        "503 service unavailable",
    ]
    for pattern in soft_error_patterns:
        if pattern in html_lower:
            return False, f"Page appears to be an error page (found: '{pattern}')"

    return True, "OK"


def resolve_url_scheme(url_without_scheme: str) -> tuple[bool, str, str]:
    """
    Tries to reach a URL by first testing https://, then falling back to http://.
    Used when the user enters a URL without a scheme (e.g. 'jotawiki.scout.ch').
    Returns (success, validated_url, message).
    """
    # Try HTTPS first
    https_url = f"https://{url_without_scheme}"
    print_n_log(f"[INFO] Trying: {https_url}")
    is_valid, message = validate_url(https_url)
    if is_valid:
        print_n_log("[INFO] Reachable via HTTPS.")
        return True, https_url, message

    print_n_log(f"   [WARN] HTTPS failed: {message}")

    # Fall back to HTTP
    http_url = f"http://{url_without_scheme}"
    print_n_log(f"[INFO] Trying: {http_url}")
    is_valid, message = validate_url(http_url)
    if is_valid:
        print_n_log("[INFO] Reachable via HTTP.")
        return True, http_url, message

    print_n_log(f"   [WARN] HTTP also failed: {message}")
    return False, "", "Could not reach the site via HTTPS or HTTP."


# ──────────────────────────────────────────────
# FILE AND FOLDER HELPERS
# ──────────────────────────────────────────────

def clear_folder(folder_path: str) -> None:
    """Deletes all files inside the given folder (not subfolders)."""
    count = 0
    for filename in os.listdir(folder_path):
        filepath = os.path.join(folder_path, filename)
        if os.path.isfile(filepath):
            os.remove(filepath)
            count += 1
    print_n_log(f"   [OK]   {folder_path}/ cleared ({count} file(s) deleted)")


def safe_filename(name: str, ext: str) -> str:
    """Creates a safe filename from a page title."""
    name = unquote(name)
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.replace(" ", "_")
    if len(name) > 200:
        name = name[:200]
    return f"{name}.{ext}"


# ──────────────────────────────────────────────
# IMAGE HELPERS
# ──────────────────────────────────────────────

def get_image_dimensions(img_tag, img_url: str) -> tuple:
    """
    Tries to determine image dimensions.
    First checks HTML width/height attributes, then falls back to
    reading the image header (first 32 KB) for PNG, JPEG, GIF.
    Returns (width, height) or (None, None).
    """
    width = img_tag.get("width")
    height = img_tag.get("height")
    if width and height:
        try:
            return int(width), int(height)
        except (ValueError, TypeError):
            pass

    try:
        resp = session.get(img_url, timeout=10, stream=True)
        resp.raise_for_status()
        header_bytes = resp.raw.read(32768)
        resp.close()

        # PNG header
        if header_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = unpack('>II', header_bytes[16:24])
            return w, h

        # JPEG: scan for SOF markers
        if header_bytes[:2] == b'\xff\xd8':
            i = 2
            while i < len(header_bytes) - 9:
                if header_bytes[i] == 0xFF:
                    marker = header_bytes[i + 1]
                    if marker in (0xC0, 0xC1, 0xC2):
                        h, w = unpack('>HH', header_bytes[i + 5:i + 9])
                        return w, h
                    else:
                        seg_len = unpack('>H', header_bytes[i + 2:i + 4])[0]
                        i += 2 + seg_len
                else:
                    i += 1

        # GIF header
        if header_bytes[:4] == b'GIF8':
            w, h = unpack('<HH', header_bytes[6:10])
            return w, h

    except Exception:
        pass

    return None, None


def extract_image_filename(img_url: str) -> str:
    """Extracts a clean image filename from various wiki URL formats."""
    parsed = urlparse(img_url)

    # DokuWiki fetch.php URL: /lib/exe/fetch.php?media=path:to:image.png
    if "fetch.php" in parsed.path:
        qs = parse_qs(parsed.query)
        media = qs.get("media", [""])[0]
        if media:
            return unquote(media.split(":")[-1])

    # Standard path-based URL
    filename = unquote(os.path.basename(parsed.path))

    # Remove MediaWiki thumbnail prefix like "300px-"
    filename = re.sub(r"^\d+px-", "", filename)

    return filename


def replace_images_with_info(soup_content) -> None:
    """
    Replaces all <img> tags with text placeholders showing
    the image filename and dimensions (width x height in pixels).
    Modifies the soup in place.
    """
    for img in soup_content.find_all("img", src=True):
        src = img["src"]
        full_url = urljoin(state.base_url, src)

        # Determine if this is a content image based on wiki type
        is_content_image = False
        if state.wiki_type == "mediawiki":
            is_content_image = "/images/" in full_url
        elif state.wiki_type == "dokuwiki":
            is_content_image = (
                "/_media/" in full_url
                or "/lib/exe/fetch.php" in full_url
                or "_media" in src
            )

        if not is_content_image:
            img.decompose()
            continue

        filename = extract_image_filename(full_url)
        w, h = get_image_dimensions(img, full_url)

        if w and h:
            placeholder = f"[Image: {filename} ({w} x {h} px)]"
        else:
            placeholder = f"[Image: {filename}]"

        img.replace_with(placeholder)
