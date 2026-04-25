"""
Wiki Downloader
==============

PURPOSE:
Creates a PDF or Markdown copy of every page on a wiki site,
and/or downloads all images (only those images which are used on the pages).

AUTHOR:
Pepe HB9EVT (Github: @pepe-hb9evt)
with support of the following A.I.: "myAI" by Swisscom, powered by Anthropic Claude.

SUPPORTED WIKI ENGINES:
- MediaWiki
- DokuWiki

PROCEDURE:
In the first step, the script generates all the PDFs or Markdown files.
At the same time, a list of all images is created. This allows the script
to detect whether an image has been used multiple times on different pages.
In the second step, all images are downloaded.
Particular feature: In Markdown mode, images are replaced with a text placeholder
showing the image filename and its dimensions (width x height in pixels).

LOGGING:
All terminal output is also appended to the log file (log_wiki_downloader.txt).
The log file is never overwritten; each run adds a new session.

PREPARATION:
pip install requests
pip install beautifulsoup4
pip install pdfkit (only for PDF output)
pip install html2text (only for Markdown output)

For PDF output, wkhtmltopdf must also be installed:
- Windows: https://wkhtmltopdf.org/downloads.html
- macOS: brew install wkhtmltopdf
- Linux: sudo apt install wkhtmltopdf
"""

import os
import time

from sub_config import (
    state,
    counters,
    OUTPUT_PDF_DIR,
    OUTPUT_MD_DIR,
    OUTPUT_IMG_DIR,
    DELAY_SECONDS,
)
from sub_helpers import (
    print_n_log,
    log_session_header,
    abort_program,
    validate_url,
    resolve_url_scheme,
    clear_folder,
)
from sub_detection import detect_wiki_type
from sub_mediawiki import get_all_page_links_mediawiki
from sub_dokuwiki import get_all_page_links_dokuwiki
from sub_download import (
    download_pdf,
    download_markdown,
    get_image_urls_from_page,
    download_image,
)

# Optional packages (checked during menu)
try:
    import pdfkit
except ImportError:
    pdfkit = None

try:
    import html2text
except ImportError:
    html2text = None


# ──────────────────────────────────────────────
# PAGE LISTING DISPATCHER
# ──────────────────────────────────────────────
def get_all_page_links() -> list[tuple[str, str]]:
    """Dispatcher: calls the appropriate page listing method based on wiki type."""
    if state.wiki_type == "mediawiki":
        return get_all_page_links_mediawiki()
    elif state.wiki_type == "dokuwiki":
        return get_all_page_links_dokuwiki()
    else:
        print_n_log("[FAIL] Unknown wiki type. Cannot list pages.")
        return []


# ──────────────────────────────────────────────
# INTERACTIVE MENU
# ──────────────────────────────────────────────
def show_menu() -> tuple[str, str]:
    """Interactive menu. Asks for wiki URL, validates it, auto-detects the engine, then asks for download scope, page format, and whether to clear output folders. Every question offers [9] Cancel to abort the program.

    Returns (download_scope, page_format).
    """
    # --- Step 1: Ask for the wiki URL and validate it ---
    print_n_log("\n[MENU] Enter the URL of the wiki you want to download.")
    print_n_log(" Examples: https://openwrt.org")
    print_n_log("           jotawiki.scout.ch")
    print_n_log(" Enter 9 to cancel.")
    while True:
        url_input = input(" Wiki URL: ").strip()
        print_n_log(f" Wiki URL: {url_input}")

        # Cancel
        if url_input == "9":
            abort_program()

        # Skip empty input
        if not url_input:
            print_n_log(" [WARN] Please enter a valid URL.")
            continue

        # Remove trailing slash
        url_input = url_input.rstrip("/")

        # Determine if the user provided a scheme or not
        has_scheme = url_input.startswith("http://") or url_input.startswith("https://")

        if has_scheme:
            # User provided a full URL with scheme: validate directly
            print_n_log(f"[INFO] Checking URL: {url_input}")
            is_valid, message = validate_url(url_input)
            if is_valid:
                print_n_log("[INFO] URL is valid.")
                state.base_url = url_input
                break
            else:
                print_n_log(f" [FAIL] {message}")
                print_n_log(" Please try again.\n")

        else:
            # No scheme provided: try https:// first, then fall back to http://
            success, validated_url, message = resolve_url_scheme(url_input)
            if success:
                state.base_url = validated_url
                break
            else:
                print_n_log(f" [FAIL] {message}")
                print_n_log(" Please try again.\n")

    print_n_log(f"[INFO] Target: {state.base_url}")

    # --- Step 2: Auto-detect wiki engine ---
    detected = detect_wiki_type(state.base_url)
    if detected:
        state.wiki_type = detected
        print_n_log(f"[INFO] Wiki engine: {state.wiki_type}")
    else:
        # Auto-detection failed: ask the user
        print_n_log("\n[WARN] Could not auto-detect the wiki engine.")
        print_n_log("[MENU] Which wiki engine does this site use?")
        print_n_log(" [1] MediaWiki")
        print_n_log(" [2] DokuWiki")
        print_n_log(" [9] Cancel")
        while True:
            choice = input(" Your choice (1/2/9): ").strip()
            print_n_log(f" Your choice (1/2/9): {choice}")
            if choice == "9":
                abort_program()
            if choice in ("1", "2"):
                break
            print_n_log(" [WARN] Please enter 1, 2, or 9.")

        state.wiki_type = "mediawiki" if choice == "1" else "dokuwiki"
        print_n_log(f"[INFO] Wiki engine: {state.wiki_type}")

    # --- Step 3: Download scope ---
    print_n_log("\n[MENU] What would you like to download?")
    print_n_log(" [1] Pages only")
    print_n_log(" [2] Images only")
    print_n_log(" [3] Both (pages and images)")
    print_n_log(" [9] Cancel")
    while True:
        choice = input(" Your choice (1/2/3/9): ").strip()
        print_n_log(f" Your choice (1/2/3/9): {choice}")
        if choice == "9":
            abort_program()
        if choice in ("1", "2", "3"):
            break
        print_n_log(" [WARN] Please enter 1, 2, 3, or 9.")

    scope_map = {"1": "pages", "2": "images", "3": "both"}
    download_scope = scope_map[choice]

    # --- Step 4: Page format (only if downloading pages) ---
    page_format = None
    if download_scope in ("pages", "both"):
        print_n_log("\n[MENU] In which format should pages be saved?")
        print_n_log(" [1] PDF")
        print_n_log(" [2] Markdown")
        print_n_log(" [9] Cancel")
        while True:
            choice = input(" Your choice (1/2/9): ").strip()
            print_n_log(f" Your choice (1/2/9): {choice}")
            if choice == "9":
                abort_program()
            if choice in ("1", "2"):
                break
            print_n_log(" [WARN] Please enter 1, 2, or 9.")

        page_format = "pdf" if choice == "1" else "markdown"

        # Verify that required packages are installed
        if page_format == "pdf" and pdfkit is None:
            print_n_log("\n [FAIL] 'pdfkit' is not installed. Run: pip install pdfkit")
            exit(1)

        if page_format == "markdown" and html2text is None:
            print_n_log("\n [FAIL] 'html2text' is not installed. Run: pip install html2text")
            exit(1)

    # --- Step 5: Ask whether to clear the affected output folders ---
    download_pages = download_scope in ("pages", "both")
    download_images = download_scope in ("images", "both")

    # Determine which folders are affected by this run
    affected_folders = []
    if download_pages and page_format == "pdf":
        affected_folders.append(OUTPUT_PDF_DIR)
    if download_pages and page_format == "markdown":
        affected_folders.append(OUTPUT_MD_DIR)
    if download_images:
        affected_folders.append(OUTPUT_IMG_DIR)

    # Only ask if at least one affected folder already contains files
    folders_with_files = [
        f
        for f in affected_folders
        if os.path.isdir(f) and any(os.path.isfile(os.path.join(f, name)) for name in os.listdir(f))
    ]
    if folders_with_files:
        print_n_log(f"\n[MENU] The following output folder(s) already contain files:")
        for f in folders_with_files:
            file_count = sum(1 for name in os.listdir(f) if os.path.isfile(os.path.join(f, name)))
            print_n_log(f" ./{f}/ ({file_count} file(s))")
        print_n_log(" Should they be cleared before downloading?")
        print_n_log(" [1] Yes, clear folder(s)")
        print_n_log(" [2] No, keep existing files (duplicates will be skipped)")
        print_n_log(" [9] Cancel")
        while True:
            choice = input(" Your choice (1/2/9): ").strip()
            print_n_log(f" Your choice (1/2/9): {choice}")
            if choice == "9":
                abort_program()
            if choice in ("1", "2"):
                break
            print_n_log(" [WARN] Please enter 1, 2, or 9.")

        if choice == "1":
            print_n_log("[INFO] Clearing output folder(s)...")
            for f in folders_with_files:
                clear_folder(f)
            print_n_log("")

    return download_scope, page_format


# ──────────────────────────────────────────────
# MAIN PROGRAM
# ──────────────────────────────────────────────
def main():
    log_session_header()
    print_n_log("=" * 55)
    print_n_log(" Wiki Downloader")
    print_n_log("=" * 55)

    download_scope, page_format = show_menu()

    download_pages = download_scope in ("pages", "both")
    download_images = download_scope in ("images", "both")

    pages = get_all_page_links()
    if not pages:
        print_n_log("[FAIL] No pages found. Exiting.")
        return

    all_image_urls: set[str] = set()
    for i, (title, url) in enumerate(pages, 1):
        print_n_log(f"[{i}/{len(pages)}] {title}")
        print_n_log(f" [URL] {url}")

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
                print_n_log(f" [SCAN] {len(imgs)} image(s) found")
            all_image_urls.update(imgs)

        time.sleep(DELAY_SECONDS)

    # Step 3: Download all collected images (if requested)
    if download_images:
        print_n_log("\n" + "=" * 55)
        print_n_log(f" Downloading {len(all_image_urls)} unique image(s)...")
        print_n_log("=" * 55)
        for img_url in sorted(all_image_urls):
            download_image(img_url)
            time.sleep(0.3)

    # -- Final summary --
    print_n_log("\n" + "=" * 55)
    print_n_log(" Done!")
    print_n_log(f" Source: {state.base_url} ({state.wiki_type})")
    if download_pages and page_format == "pdf":
        print_n_log(f" PDFs: ./{OUTPUT_PDF_DIR}/")
        print_n_log(f" Saved: {counters.pdfs_saved}")
        print_n_log(f" Skipped: {counters.pdfs_skipped}")
        print_n_log(f" Failed: {counters.pdfs_failed}")
    if download_pages and page_format == "markdown":
        print_n_log(f" Markdown: ./{OUTPUT_MD_DIR}/")
        print_n_log(f" Saved: {counters.mds_saved}")
        print_n_log(f" Skipped: {counters.mds_skipped}")
        print_n_log(f" Failed: {counters.mds_failed}")
    if download_images:
        print_n_log(f" Images: ./{OUTPUT_IMG_DIR}/")
        print_n_log(f" Saved: {counters.imgs_saved}")
        print_n_log(f" Skipped: {counters.imgs_skipped}")
        print_n_log(f" Failed: {counters.imgs_failed}")
    print_n_log("=" * 55)


if __name__ == "__main__":
    main()
