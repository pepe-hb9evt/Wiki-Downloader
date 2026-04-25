# Wiki Downloader

## What does this program do?

The **Wiki Downloader** creates local copies of wiki pages and their images. It reads all pages of a wiki and saves them as **PDF** or **Markdown files**. Additionally, all **images** used on the pages can be downloaded.

---

## Supported Wiki Engines

| Wiki Engine | Detection | Page Listing |
|---|---|---|
| **MediaWiki** (e.g. Wikipedia, jotawiki.scout.ch) | Automatic | Via special page "All Pages" |
| **DokuWiki** (e.g. openwrt.org) | Automatic | Via sitemap, index, or crawling |

The wiki engine is **automatically detected** at startup. If detection fails, the wiki type can be selected manually.

---

## Features

- **Save pages as PDF** -- Creates one PDF document per wiki page.
- **Save pages as Markdown** -- Converts each page into a `.md` file. Images are replaced with a placeholder showing the filename and image dimensions (width x height in pixels).
- **Download images** -- Saves all images embedded in wiki pages locally. Only content images are included, not icons or UI elements.
- **Skip existing files** -- The program detects whether a file already exists and skips it. This allows an interrupted run to be resumed.
- **Clear output folders** -- Before downloading, users can choose to delete existing files in the target folders.
- **Log file** -- All terminal output is additionally written to a log file that is never overwritten.

---

## Usage

The program is started in the terminal and guides the user through an interactive menu:

1. **Enter URL** -- The address of the wiki (e.g. `jotawiki.scout.ch`). If no `http://` or `https://` is provided, the program automatically tests HTTPS first, then falls back to HTTP.
2. **Wiki engine** -- Detected automatically. Manual selection if detection fails.
3. **What to download?** -- Pages, images, or both.
4. **Choose format** -- PDF or Markdown (only for page downloads).
5. **Clear folders?** -- If files already exist in the target folders, they can be deleted first.

At every prompt, entering **9** cancels the program.

---

## Output Folders

| Folder | Content |
|---|---|
| `output_pdf_pages/` | PDF files of wiki pages |
| `output_markdown_pages/` | Markdown files of wiki pages |
| `output_images/` | Downloaded images |

---

## Prerequisites

### Python Packages

    pip install requests beautifulsoup4
    pip install pdfkit       # only for PDF output
    pip install html2text    # only for Markdown output

### External Software (PDF only)

The program **wkhtmltopdf** must be installed:

| System | Installation |
|---|---|
| Windows | Installer from https://wkhtmltopdf.org/downloads.html |
| macOS | `brew install wkhtmltopdf` |
| Linux | `sudo apt install wkhtmltopdf` |

Note: If you only use Markdown and/or images, you do not need `pdfkit` or `wkhtmltopdf`.

---

## Limitations and Known Constraints

### General

- **Only publicly accessible wikis** -- The program cannot download pages behind a login.
- **Bot protection** -- Some wikis use protection mechanisms like Cloudflare or Anubis that block automated access. In such cases, the download will fail.
- **Server load** -- The program inserts a pause between requests (default: 1 second) to avoid overloading the server. For large wikis with thousands of pages, the process may take a considerable amount of time.
- **No versioning** -- Only the current version of a page is saved, not the revision history.

### PDF Output

- **Layout differences** -- The PDF rendering may differ from the browser layout, as `wkhtmltopdf` renders the page without JavaScript.
- **Missing fonts** -- On some systems, special characters may be missing if the required fonts are not installed.

### Markdown Output

- **Conversion losses** -- Complex HTML structures such as nested tables or forms may not be perfectly converted to Markdown.
- **Images as placeholders** -- Images are not embedded in the Markdown but replaced with a text placeholder (e.g. `[Image: Photo.jpg (640 x 480 px)]`).

### DokuWiki-specific

- **Sitemap not always enabled** -- Some DokuWiki installations have the sitemap disabled. The program then uses the index (`?do=index`) or recursive crawling as a last resort.
- **URL rewriting** -- DokuWiki instances with URL rewriting enabled may behave differently. The program attempts to detect various URL formats.

### MediaWiki-specific

- **Language-dependent special pages** – The program automatically tries both the German (Spezial:Alle_Seiten) and English (Special:AllPages) paths for the “All Pages” special page. For wikis in other languages, the constants ALL_PAGES_PATH_1 and ALL_PAGES_PATH_2 in the configuration must be adjusted.
---

## Author

**Pepe HB9EVT** (GitHub: [@pepe-hb9evt](https://github.com/pepe-hb9evt))

Developed with the support of **myAI** (Swisscom), powered by Anthropic Claude.
