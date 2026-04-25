# Wiki Downloader -- Bedienungsanleitung

## Was macht dieses Programm?

Der **Wiki Downloader** erstellt lokale Kopien von Wiki-Seiten und deren Bildern. Er liest alle Seiten eines Wikis aus und speichert sie wahlweise als **PDF** oder **Markdown-Datei**. Zusätzlich können alle auf den Seiten verwendeten **Bilder** heruntergeladen werden.

---

## Unterstützte Wiki-Systeme

| Wiki-Engine | Erkennung | Seitenlisting |
|---|---|---|
| **MediaWiki** (z.B. Wikipedia, jotawiki.scout.ch) | Automatisch | Über Spezialseite "Alle Seiten" |
| **DokuWiki** (z.B. openwrt.org) | Automatisch | Über Sitemap, Index oder Crawling |

Die Wiki-Engine wird beim Start **automatisch erkannt**. Sollte die Erkennung fehlschlagen, kann der Wiki-Typ manuell gewählt werden.

---

## Funktionsumfang

- **Seiten als PDF speichern** -- Erstellt ein PDF-Dokument pro Wiki-Seite.
- **Seiten als Markdown speichern** -- Konvertiert jede Seite in eine `.md`-Datei. Bilder werden dabei durch einen Platzhalter ersetzt, der den Dateinamen und die Bildgrösse (Breite x Höhe in Pixel) anzeigt.
- **Bilder herunterladen** -- Speichert alle auf den Wiki-Seiten eingebetteten Bilder lokal. Dabei werden nur Inhaltsbilder berücksichtigt, keine Icons oder UI-Elemente.
- **Bereits vorhandene Dateien überspringen** -- Das Programm erkennt, ob eine Datei bereits existiert und überspringt sie. Dadurch kann ein abgebrochener Lauf fortgesetzt werden.
- **Output-Ordner leeren** -- Vor dem Download kann gewählt werden, ob bestehende Dateien in den Zielordnern gelöscht werden sollen.
- **Protokolldatei** -- Alle Terminal-Ausgaben werden zusätzlich in eine Log-Datei geschrieben, die nie überschrieben wird.

---

## Bedienung

Das Programm wird im Terminal gestartet und führt den Benutzer durch ein interaktives Menü:

1. **URL eingeben** -- Die Adresse des Wikis (z.B. `jotawiki.scout.ch`). Wenn kein `http://` oder `https://` angegeben wird, testet das Programm automatisch zuerst HTTPS und dann HTTP.
2. **Wiki-Engine** -- Wird automatisch erkannt. Bei Fehlschlag manuelle Auswahl.
3. **Was herunterladen?** -- Seiten, Bilder oder beides.
4. **Format wählen** -- PDF oder Markdown (nur bei Seitendownload).
5. **Ordner leeren?** -- Falls bereits Dateien in den Zielordnern vorhanden sind, kann man diese vorher löschen lassen.

Bei jeder Frage kann mit **9** abgebrochen werden.

---

## Ausgabe-Ordner

| Ordner | Inhalt |
|---|---|
| `output_pdf_pages/` | PDF-Dateien der Wiki-Seiten |
| `output_markdown_pages/` | Markdown-Dateien der Wiki-Seiten |
| `output_images/` | Heruntergeladene Bilder |

---

## Voraussetzungen

### Python-Pakete

    pip install requests beautifulsoup4
    pip install pdfkit       # nur für PDF-Ausgabe
    pip install html2text    # nur für Markdown-Ausgabe

### Externe Software (nur für PDF)

Das Programm **wkhtmltopdf** muss installiert sein:

| System | Installation |
|---|---|
| Windows | Installer von https://wkhtmltopdf.org/downloads.html |
| macOS | `brew install wkhtmltopdf` |
| Linux | `sudo apt install wkhtmltopdf` |

Hinweis: Wer nur Markdown und/oder Bilder nutzt, braucht weder `pdfkit` noch `wkhtmltopdf`.

---

## Einschränkungen und bekannte Grenzen

### Allgemein

- **Nur öffentlich zugängliche Wikis** -- Das Programm kann keine Seiten hinter einem Login herunterladen.
- **Bot-Schutz** -- Manche Wikis verwenden Schutzmechanismen wie Cloudflare oder Anubis, die automatisierte Zugriffe blockieren. In solchen Fällen schlägt der Download fehl.
- **Serverlast** -- Das Programm fügt zwischen den Anfragen eine Pause ein (standardmässig 1 Sekunde), um den Server nicht zu überlasten. Bei grossen Wikis mit tausenden Seiten kann der Vorgang daher entsprechend lange dauern.
- **Keine Versionierung** -- Es wird immer nur die aktuelle Version einer Seite gespeichert, nicht die Änderungshistorie.

### PDF-Ausgabe

- **Layout-Abweichungen** -- Die PDF-Darstellung kann vom Browser-Layout abweichen, da `wkhtmltopdf` die Seite ohne JavaScript rendert.
- **Fehlende Schriften** -- Auf manchen Systemen können Sonderzeichen fehlen, wenn die benötigten Schriftarten nicht installiert sind.

### Markdown-Ausgabe

- **Konvertierungsverluste** -- Komplexe HTML-Strukturen wie verschachtelte Tabellen oder Formulare werden möglicherweise nicht perfekt in Markdown umgewandelt.
- **Bilder als Platzhalter** -- Bilder werden nicht in das Markdown eingebettet, sondern durch einen Textplatzhalter ersetzt (z.B. `[Image: Foto.jpg (640 x 480 px)]`).

### DokuWiki-spezifisch

- **Sitemap nicht immer aktiviert** -- Manche DokuWiki-Installationen haben die Sitemap deaktiviert. Das Programm nutzt dann den Index (`?do=index`) oder als letzten Ausweg rekursives Crawling.
- **URL-Rewriting** -- DokuWiki-Instanzen mit aktiviertem URL-Rewriting können sich unterschiedlich verhalten. Das Programm versucht, verschiedene URL-Formate zu erkennen.

### MediaWiki-spezifisch

- **Sprachabhängige Spezialseiten** -- Das Programm versucht automatisch sowohl den deutschen (`Spezial:Alle_Seiten`) als auch den englischen (`Special:AllPages`) Pfad für die Spezialseite "Alle Seiten". Für Wikis in anderen Sprachen müssen die Konstanten `ALL_PAGES_PATH_1` und `ALL_PAGES_PATH_2` in der Konfigurationsdatei angepasst werden.

---

## Autor

**Pepe HB9EVT** (GitHub: [@pepe-hb9evt](https://github.com/pepe-hb9evt))

Entwickelt mit Unterstützung von **myAI** (Swisscom), powered by Anthropic Claude.
