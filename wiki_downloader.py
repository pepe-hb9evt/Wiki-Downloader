"""
Wiki Downloader
===============

Authors:
- Pepe
- AI: Swisscom myAI (powered by Anthropic Claude)

Purpose:
Creates a PDF copy of every page on a MediaWiki site,
and downloads all images (only those images which are
used on the pages)

Procedure:
In the first step, the script generates all the PDFs.
At the same time, a list of all images is created.
This allows the script to detect whether an image has been
used multiple times on different pages.
In the second step, all images are downloaded.

Preparation:
Please check in the lines below which additional python packages
and which external app (!) is needed.
"""

# Standard packages
import os
import re
import time
from urllib.parse import urljoin, urlparse, unquote

# Packages to be installed
import requests
import pdfkit
from bs4 import BeautifulSoup # name of package: beautifulsoup4

# Software App to be installed
#
# App 'wkhtmltopdf' must be installed:
# - Windows: https://wkhtmltopdf.org/downloads.html
# - macOS:   brew install wkhtmltopdf
# - Linux:   sudo apt install wkhtmltopdf


# ──────────────────────────────────────────────
# CONFIGURATION
# ──────────────────────────────────────────────
BASE_URL        = "http://jotawiki.scout.ch"
ALL_PAGES_URL   = f"{BASE_URL}/index.php?title=Spezial:Alle_Seiten"
OUTPUT_PDF_DIR  = "wiki_pdfs"       # Folder for PDFs
OUTPUT_IMG_DIR  = "wiki_images"     # Folder for images
DELAY_SECONDS   = 1.0               # Pause between requests (to be kind to the server)

# wkhtmltopdf path (only needed if not in PATH, e.g. on Windows)
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
# WKHTMLTOPDF_PATH = None             # None = auto-detect from PATH


# ──────────────────────────────────────────────
# SETUP
# ──────────────────────────────────────────────
os.makedirs(OUTPUT_PDF_DIR, exist_ok=True)
os.makedirs(OUTPUT_IMG_DIR, exist_ok=True)

session = requests.Session()
session.headers.update({"User-Agent": "WikiDownloader/1.0 (educational use)"})

pdf_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH) if WKHTMLTOPDF_PATH else None

pdf_options = {
    "encoding":           "UTF-8",
    "print-media-type":   "",
    "no-background":      "",
    "quiet":              "",
}


# ──────────────────────────────────────────────
# HELPER FUNCTIONS
# ──────────────────────────────────────────────
def safe_filename(name: str, ext: str) -> str:
    """Creates a safe filename from a page title."""
    name = unquote(name)
    name = re.sub(r'[\\/*?:"<>|]', "_", name)
    name = name.replace(" ", "_")
    return f"{name}.{ext}"


def get_all_page_links() -> list[tuple[str, str]]:
    """
    Reads all page links from Spezial:Alle_Seiten.
    Returns a list of (title, URL) tuples.
    """
    print(f"📋 Loading page list from: {ALL_PAGES_URL}")
    resp = session.get(ALL_PAGES_URL, timeout=15)
    resp.raise_for_status()

    soup = BeautifulSoup(resp.text, "html.parser")
    pages = []

    # MediaWiki lists pages inside <ul class="mw-allpages-chunk">
    for ul in soup.select("ul.mw-allpages-chunk"):
        for a in ul.find_all("a", href=True):
            title = a.get_text(strip=True)
            url   = urljoin(BASE_URL, a["href"])
            pages.append((title, url))

    # Fallback: collect all links from the content area
    if not pages:
        content = soup.find("div", id="mw-content-text") or soup
        for a in content.find_all("a", href=True):
            href = a["href"]
            if href.startswith("/index.php?title=") and "Spezial:" not in href:
                title = a.get_text(strip=True)
                url   = urljoin(BASE_URL, href)
                if title:
                    pages.append((title, url))

    print(f"   → {len(pages)} pages found.\n")
    return pages


def download_pdf(title: str, url: str) -> None:
    """Saves a wiki page as a PDF file."""
    filename = safe_filename(title, "pdf")
    filepath = os.path.join(OUTPUT_PDF_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"   ⏭️  PDF already exists, skipping: {filename}")
        return

    try:
        kwargs = {"options": pdf_options}
        if pdf_config:
            kwargs["configuration"] = pdf_config

        pdfkit.from_url(url, filepath, **kwargs)
        print(f"   ✅ PDF saved: {filename}")
    except Exception as e:
        print(f"   ❌ PDF error ({title}): {e}")


def get_image_urls_from_page(page_url: str) -> list[str]:
    """Extracts all image URLs from the content of a wiki page."""
    try:
        resp = session.get(page_url, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"   ⚠️  Page not reachable: {e}")
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
            # e.g. /images/thumb/a/ab/Photo.jpg/300px-Photo.jpg → /images/a/ab/Photo.jpg
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
    filename = unquote(os.path.basename(urlparse(img_url).path))
    filename = re.sub(r'[\\/*?:"<>|]', "_", filename)
    filepath = os.path.join(OUTPUT_IMG_DIR, filename)

    # Skip if file already exists
    if os.path.exists(filepath):
        print(f"      ⏭️  Image already exists: {filename}")
        return

    try:
        resp = session.get(img_url, timeout=15, stream=True)
        resp.raise_for_status()
        with open(filepath, "wb") as f:
            for chunk in resp.iter_content(8192):
                f.write(chunk)
        print(f"      🖼️  Image saved: {filename}")
    except Exception as e:
        print(f"      ❌ Image error ({img_url}): {e}")


# ──────────────────────────────────────────────
# MAIN PROGRAM
# ──────────────────────────────────────────────
def main():
    print("=" * 55)
    print("  JOTA-JOTI Wiki Downloader")
    print("=" * 55)

    pages = get_all_page_links()

    all_image_urls: set[str] = set()

    for i, (title, url) in enumerate(pages, 1):
        print(f"[{i}/{len(pages)}] 📄 {title}")
        print(f"   🔗 {url}")

        # Step 1: Save page as PDF
        download_pdf(title, url)

        # Step 2: Collect all image URLs found on the page
        imgs = get_image_urls_from_page(url)
        if imgs:
            print(f"   🔍 {len(imgs)} image(s) found")
            all_image_urls.update(imgs)

        time.sleep(DELAY_SECONDS)

    # Step 3: Download all collected images
    print("\n" + "=" * 55)
    print(f"  📥 Downloading {len(all_image_urls)} unique image(s)...")
    print("=" * 55)

    for img_url in sorted(all_image_urls):
        download_image(img_url)
        time.sleep(0.3)

    print("\n" + "=" * 55)
    print(f"  🎉 Done!")
    print(f"  📁 PDFs:   ./{OUTPUT_PDF_DIR}/")
    print(f"  📁 Images: ./{OUTPUT_IMG_DIR}/")
    print("=" * 55)


if __name__ == "__main__":
    main()
