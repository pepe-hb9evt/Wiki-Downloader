"""
Wiki Downloader
==============

AUTHOR:
Pepe HB9EVT (GitHub: @pepe-hb9evt)
with support of the following A.I.:
"myAI" by Swisscom, powered by Anthropic Claude.

PURPOSE:
Creates a PDF or Markdown copy of every page on a MediaWiki site,
and/or downloads all images (only those images which are used on the pages).

PROCEDURE:
In the first step, the script generates all the PDFs or Markdown files.
At the same time, a list of all images is created.
This allows the script to detect whether an image has been used multiple
times on different pages.
In the second step, all images are downloaded.

PREPARATION:
Please check in the lines below which additional python packages and
which external app (!) is needed.
"""

# Standard packages
import os
import re
import time
from urllib.parse import urljoin, urlparse, unquote

# Packages to be installed
import requests
from bs4 import BeautifulSoup # name of package: beautifulsoup4

import pdfkit    # only needed for PDF output
import html2text # only needed for MarkDown output


# External app (only needed for PDF output)
#
# App 'wkhtmltopdf' must be installed:
# - Windows: https://wkhtmltopdf.org/downloads.html
# - macOS:   brew install wkhtmltopdf
# - Linux:   sudo apt install wkhtmltopdf


# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────

BASE_URL = "http://jotawiki.scout.ch"
ALL_PAGES_URL = f"{BASE_URL}/index.php?title=Spezial:Alle_Seiten"
OUTPUT_PDF_DIR = "output_pdf_pages"  # Folder for PDFs
OUTPUT_MD_DIR =  "output_markdown_pages"  # Folder for Markdown files
OUTPUT_IMG_DIR = "output_images"  # Folder for images
DELAY_SECONDS = 1.0  # Pause between requests (to be kind to the server)

# wkhtmltopdf path (only needed if not in PATH, e.g. on Windows)
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
# WKHTMLTOPDF_PATH = None  # None = auto-detect from PATH


# ──────────────────────────────────────────────
# SETUP
# ──────────────────────────────────────────────
os.makedirs(OUTPUT_PDF_DIR, exist_ok=True)
os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(OUTPUT_IMG_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "WikiDownloader/1.0 (educational use)"})

pdf_options = {
    "encoding": "UTF-8",
    "print-media-type": "",
    "no-background": "",
    "quiet": "",
}

# ──────────────────────────────────────────────
# COUNTERS
# ──────────────────────────────────────────────
counter_pdfs_saved = 0  # Number of PDFs successfully saved
counter_pdfs_skipped = 0  # Number of PDFs skipped (already existed)
counter_pdfs_failed = 0  # Number of PDFs that failed

counter_mds_saved = 0  # Number of Markdown files successfully saved
counter_mds_skipped = 0  # Number of Markdown files skipped (already existed)
counter_mds_failed = 0  # Number of Markdown files that failed

counter_imgs_saved = 0  # Number of images successfully saved
counter_imgs_skipped = 0  # Number of images skipped (already existed)
counter_imgs_failed = 0  # Number of images that failed

# ──────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────

def safe_filename(name: str, ext: str) -> str:
    """Creates a safe filename from a page title."""
    name = unquote(name)
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.replace(" ", "_")
    return f"{name}.{ext}"


def get_image_dimensions(img_tag, img_url: str) -> tuple[int | None, int | None]:
    """
    Tries to determine image dimensions.
    First checks HTML width/height attributes, then falls back to
    downloading the image header to read actual pixel dimensions.
    Returns (width, height) or (None, None) if not determinable.
    """
    # Try HTML attributes first
    width = img_tag.get("width")
    height = img_tag.get("height")

    if width and height:
        try:
            return int(width), int(height)
        except (ValueError, TypeError):
            pass

    # Fallback: download image header and read dimensions
    try:
        resp = session.get(img_url, timeout=10, stream=True)
        resp.raise_for_status()

        # Read first 32 KB (enough for image headers)
        header_bytes = resp.raw.read(32768)
        resp.close()

        from struct import unpack

        # PNG: bytes 16-23 contain width and height as 4-byte big-endian ints
        if header_bytes[:8] == b'\x89PNG\r\n\x1a\n':
            w, h = unpack('>II', header_bytes[16:24])
            return w, h

        # JPEG: scan for SOF markers
        if header_bytes[:2] == b'\xff\xd8':
            i = 2
            while i < len(header_bytes) - 9:
                if header_bytes[i] == 0xFF:
                    marker = header_bytes[i + 1]
                    # SOF0, SOF1, SOF2 markers
                    if marker in (0xC0, 0xC1, 0xC2):
                        h, w = unpack('>HH', header_bytes[i + 5:i + 9])
                        return w, h
                    else:
                        seg_len = unpack('>H', header_bytes[i + 2:i + 4])[0]
                        i += 2 + seg_len
                else:
                    i += 1

        # GIF: bytes 6-9 contain width and height as 2-byte little-endian ints
        if header_bytes[:4] in (b'GIF8',):
            w, h = unpack('<HH', header_bytes[6:10])
            return w, h

    except Exception:
        pass

    return None, None


def replace_images_with_info(soup_content) -> None:
    """
    Replaces all <img> tags in the soup content with a text placeholder
    showing the image filename and dimensions (width x height in pixels).
    Modifies the soup in place.
    """
    for img in soup_content.find_all("img", src=True):
        src = img["src"]
        full_url = urljoin(BASE_URL, src)

        # Only process content images
        if "/images/" not in full_url:
            img.decompose()
            continue

        # Extract original filename
        filename = unquote(os.path.basename(urlparse(full_url).path))
        # Remove thumbnail prefix like "300px-"
        filename = re.sub(r"^\d+px-", "", filename)

        # Get dimensions
        w, h = get_image_dimensions(img, full_url)

        if w and h:
            placeholder = f"[Image: {filename} ({w} x {h} px)]"
        else:
            placeholder = f"[Image: {filename}]"

        # Replace <img> tag with text placeholder
        img.replace_with(placeholder)


def get_all_page_links() -> list[tuple[str, str]]:
    """Reads all page links from Spezial:Alle_Seiten.
    Returns a list of (title, URL) tuples."""
    print(f"[INFO] Loading page list from: {ALL_PAGES_URL}")
    resp = session.get(ALL_PAGES_URL, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    pages = []

    # MediaWiki lists pages inside <ul class="mw-allpages-chunk">
    for ul in soup.select("ul.mw-allpages-chunk"):
        for a in ul.find_all("a", href=True):
            title = a.get_text(strip=True)
            url = urljoin(BASE_URL, a["href"])
            pages.append((title, url))

    # Fallback: collect all links from the content area
    if not pages:
        content = soup.find("div", id="mw-content-text") or soup
        for a in content.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/index.php?title=") and "Spezial:" not in href:
                title = a.get_text(strip=True)
                url = urljoin(BASE_URL, href)
                if title:
                    pages.append((title, url))

    print(f"       -> {len(pages)} pages found.\n")
    return pages


def download_pdf(title: str, url: str) -> None:
    """Saves a wiki page as a PDF file."""
    global counter_pdfs_saved, counter_pdfs_skipped, counter_pdfs_failed

    filename = safe_filename(title, "pdf")
    filepath = os.path.join(OUTPUT_PDF_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"   [SKIP] PDF already exists: {filename}")
        counter_pdfs_skipped += 1
        return

    try:
        kwargs = {"options": pdf_options}
        if pdf_config:
            kwargs["configuration"] = pdf_config
        pdfkit.from_url(url, filepath, **kwargs)
        print(f"   [OK]   PDF saved: {filename}")
        counter_pdfs_saved += 1
    except Exception as e:
        print(f"   [FAIL] PDF error ({title}): {e}")
        counter_pdfs_failed += 1


def download_markdown(title: str, url: str) -> None:
    """Saves a wiki page as a Markdown file.
    Images are replaced with a placeholder showing filename and dimensions."""
    global counter_mds_saved, counter_mds_skipped, counter_mds_failed

    filename = safe_filename(title, "md")
    filepath = os.path.join(OUTPUT_MD_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"   [SKIP] Markdown already exists: {filename}")
        counter_mds_skipped += 1
        return

    try:
        resp = session.get(url, timeout=15)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")

        # Extract only the page content area
        content = soup.find("div", id="mw-content-text")
        if not content:
            content = soup.find("div", id="bodyContent")
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
        counter_mds_saved += 1
    except Exception as e:
        print(f"   [FAIL] Markdown error ({title}): {e}")
        counter_mds_failed += 1


def get_image_urls_from_page(page_url: str) -> list[str]:
    """Extracts all image URLs from the content of a wiki page."""
    try:
        resp = session.get(page_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"   [WARN] Page not reachable: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    content = soup.find("div", id="mw-content-text") or soup

    image_urls = []

    for img in content.find_all("img", src=True):
        src = img["src"]
        full_url = urljoin(BASE_URL, src)

        # Only include actual content images (not icons or UI elements)
        if "/images/" in full_url and "thumb" not in full_url.split("/images/")[1][:10]:
            image_urls.append(full_url)
        elif "/images/thumb/" in full_url:
            # Derive original image URL from thumbnail URL:
            # e.g. /images/thumb/a/ab/Photo.jpg/300px-Photo.jpg -> /images/a/ab/Photo.jpg
            match = re.match(r"(.*/images/(?:thumb/)?./../)([^/]+\.\w+)", full_url)
            if match:
                original = f"{BASE_URL}/images/{full_url.split('/images/thumb/')[1]}"
                # Remove the trailing /NNNpx-filename part
                original = re.sub(r"/\d+px-[^/]+$", "", original)
                image_urls.append(original)
            else:
                image_urls.append(full_url)

    return list(set(image_urls))  # Remove duplicates


def download_image(img_url: str) -> None:
    """Downloads an image and saves it locally."""
    global counter_imgs_saved, counter_imgs_skipped, counter_imgs_failed

    filename = unquote(os.path.basename(urlparse(img_url).path))
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    filepath = os.path.join(OUTPUT_IMG_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"   [SKIP] Image already exists: {filename}")
        counter_imgs_skipped += 1
        return

    try:
        resp = session.get(img_url, timeout=15, stream=True)
        resp.raise_for_status()

        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)

        print(f"   [OK]   Image saved: {filename}")
        counter_imgs_saved += 1
    except Exception as e:
        print(f"   [FAIL] Image error ({img_url}): {e}")
        counter_imgs_failed += 1


def show_menu() -> tuple[str, str]:
    """Displays an interactive menu. Returns (download_scope, page_format)."""
    print("\n[MENU] What would you like to download?")
    print("   [1] Pages only")
    print("   [2] Images only")
    print("   [3] Both (pages and images)")

    while True:
        choice = input("   Your choice (1/2/3): ").strip()
        if choice in ("1", "2", "3"):
            break
        print("   [WARN] Please enter 1, 2, or 3.")

    scope_map = {"1": "pages", "2": "images", "3": "both"}
    download_scope = scope_map[choice]

    page_format = None
    if download_scope in ("pages", "both"):
        print("\n[MENU] In which format should pages be saved?")
        print("   [1] PDF")
        print("   [2] Markdown")

        while True:
            choice = input("   Your choice (1/2): ").strip()
            if choice in ("1", "2"):
                break
            print("   [WARN] Please enter 1 or 2.")

        page_format = "pdf" if choice == "1" else "markdown"

        # Check if the required package is available
        if page_format == "pdf" and pdfkit is None:
            print("\n   [FAIL] Error: 'pdfkit' is not installed. Run: pip install pdfkit")
            exit(1)
        if page_format == "markdown" and html2text is None:
            print("\n   [FAIL] Error: 'html2text' is not installed. Run: pip install html2text")
            exit(1)

    print()
    return download_scope, page_format


# ──────────────────────────────────────────────
# MAIN PROGRAM
# ──────────────────────────────────────────────

def main():
    print("=" * 55)
    print(" JOTA-JOTI Wiki Downloader")
    print("=" * 55)

    download_scope, page_format = show_menu()
    download_pages = download_scope in ("pages", "both")
    download_images = download_scope in ("images", "both")

    pages = get_all_page_links()

    all_image_urls: set[str] = set()

    for i, (title, url) in enumerate(pages, 1):
        print(f"[{i}/{len(pages)}] {title}")
        print(f"   [URL]  {url}")

        # Step 1: Save page as PDF or Markdown (if requested)
        if download_pages:
            if page_format == "pdf":
                download_pdf(title, url)
            else:
                download_markdown(title, url)

        # Step 2: Collect all image URLs found on the page (if requested)
        if download_images:
            imgs = get_image_urls_from_page(url)
            if imgs:
                print(f"   [SCAN] {len(imgs)} image(s) found")
            all_image_urls.update(imgs)

        time.sleep(DELAY_SECONDS)

    # Step 3: Download all collected images (if requested)
    if download_images:
        print("\n" + "=" * 55)
        print(f" Downloading {len(all_image_urls)} unique image(s)...")
        print("=" * 55)

        for img_url in sorted(all_image_urls):
            download_image(img_url)
            time.sleep(0.3)

    # -- Final summary --
    print("\n" + "=" * 55)
    print(" Done!")

    if download_pages and page_format == "pdf":
        print(f" PDFs:     ./{OUTPUT_PDF_DIR}/")
        print(f"   Saved:   {counter_pdfs_saved}")
        print(f"   Skipped: {counter_pdfs_skipped}")
        print(f"   Failed:  {counter_pdfs_failed}")

    if download_pages and page_format == "markdown":
        print(f" Markdown: ./{OUTPUT_MD_DIR}/")
        print(f"   Saved:   {counter_mds_saved}")
        print(f"   Skipped: {counter_mds_skipped}")
        print(f"   Failed:  {counter_mds_failed}")

    if download_images:
        print(f" Images:   ./{OUTPUT_IMG_DIR}/")
        print(f"   Saved:   {counter_imgs_saved}")
        print(f"   Skipped: {counter_imgs_skipped}")
        print(f"   Failed:  {counter_imgs_failed}")

    print("=" * 55)


if __name__ == "__main__":
    main()
