"""
config.py
=========
Global configuration, constants, session setup, and shared runtime state.
"""

import os

import requests

# Optional packages (install depending on your chosen output format)
try:
    import pdfkit
except ImportError:
    pdfkit = None

# ──────────────────────────────────────────────
# CONSTANTS
# ──────────────────────────────────────────────
OUTPUT_PDF_DIR = "wiki_pdfs"
OUTPUT_MD_DIR = "wiki_markdown"
OUTPUT_IMG_DIR = "wiki_images"
DELAY_SECONDS = 1.0

# MediaWiki-specific: path to the "All pages" special page
# Common variants: "/index.php?title=Spezial:Alle_Seiten" (German)
#                  "/index.php?title=Special:AllPages"     (English)
MEDIAWIKI_ALL_PAGES_PATH = "/index.php?title=Spezial:Alle_Seiten"

# DokuWiki-specific: max pages to discover during recursive crawling (fallback)
DOKUWIKI_MAX_CRAWL_PAGES = 10000

# wkhtmltopdf path (only needed for PDF output, if not in system PATH)
WKHTMLTOPDF_PATH = r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
# WKHTMLTOPDF_PATH = None  # None = auto-detect from PATH

PDF_OPTIONS = {
    "encoding": "UTF-8",
    "print-media-type": "",
    "no-background": "",
    "quiet": "",
}

# ──────────────────────────────────────────────
# FOLDER SETUP
# ──────────────────────────────────────────────
os.makedirs(OUTPUT_PDF_DIR, exist_ok=True)
os.makedirs(OUTPUT_MD_DIR, exist_ok=True)
os.makedirs(OUTPUT_IMG_DIR, exist_ok=True)

# ──────────────────────────────────────────────
# HTTP SESSION
# ──────────────────────────────────────────────
session = requests.Session()
session.headers.update({"User-Agent": "WikiDownloader/1.0 (educational use)"})

# ──────────────────────────────────────────────
# PDFKIT SETUP
# ──────────────────────────────────────────────
if pdfkit:
    pdf_config = pdfkit.configuration(wkhtmltopdf=WKHTMLTOPDF_PATH) if WKHTMLTOPDF_PATH else None
else:
    pdf_config = None


# ──────────────────────────────────────────────
# RUNTIME STATE
# ──────────────────────────────────────────────
class RuntimeState:
    """Stores runtime configuration set during menu interaction."""
    def __init__(self):
        self.base_url = ""
        self.wiki_type = None  # "mediawiki" or "dokuwiki"


# ──────────────────────────────────────────────
# DOWNLOAD COUNTERS
# ──────────────────────────────────────────────
class DownloadCounters:
    """Tracks download statistics across all modules."""
    def __init__(self):
        self.pdfs_saved = 0
        self.pdfs_skipped = 0
        self.pdfs_failed = 0
        self.mds_saved = 0
        self.mds_skipped = 0
        self.mds_failed = 0
        self.imgs_saved = 0
        self.imgs_skipped = 0
        self.imgs_failed = 0


# Shared instances (imported by all other modules)
state = RuntimeState()
counters = DownloadCounters()
