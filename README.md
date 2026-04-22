# Wiki Downloader

## Author
Pepe HB9EVT
(Github: @pepe-hb9evt)

with support of  the following A.I.:
"myAI" by Swisscom, powered by Anthropic Claude.

---



## Purpose
Creates a PDF copy of every page on a MediaWiki site,
and downloads all images (only those images which are
used on the pages)

---



## Procedure
In the first step, the script generates all the PDFs (The python script uses an external app to create the PDF documents).
At the same time, a list of all images is created. This allows the script to detect whether an image has been
used multiple times on different pages.
In the second step, all images are downloaded.

If you run the script repeatedly, PDFs and images that are already present in the download folders will not be generated again.
**PLEASE NOTE:** The script does not check whether the content of the original has changed from the existing copy.

---



## Preparation
The script uses the app 'wkhtmltopdf' which must be installed:
- Windows: https://wkhtmltopdf.org/downloads.html
- macOS:   brew install wkhtmltopdf
- Linux:   sudo apt install wkhtmltopdf

---



## License

MIT License for Software
