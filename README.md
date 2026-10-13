# Nicolas Schützinger — Website (Nachbau der Wix-Seite)

Stand: 13.10.2026. Testfassung zum Zeigen, online unter https://cindygravity.github.io/nico-website-test/ (`noindex` ist gesetzt). Die offizielle Seite bleibt die bei Wix.

## Bilder pflegen: „Website bearbeiten"

Doppelklick auf **`Website bearbeiten.command`**. Der Browser öffnet die Seite mit einer dunklen Leiste oben.

- **Hinzufügen:** In einer Galerie Bilder auf die Fläche „+ Bilder hinzufügen" ziehen oder sie anklicken. Mehrere auf einmal gehen. Neue Bilder stehen vorn.
- **Angaben:** Bild anklicken. Rechts stehen Titel, Maße, Jahr, Technik und „private collection". Gespeichert wird von selbst.
- **Reihenfolge:** Bild an die neue Stelle ziehen.
- **Löschen:** Bild anklicken, „Bild löschen", zur Bestätigung noch einmal klicken.
- **Verwerfen:** setzt alles auf den zuletzt veröffentlichten Stand zurück.
- **Veröffentlichen:** lädt den Stand hoch. Etwa eine Minute später ist er online.

Bis zum Klick auf „Veröffentlichen" ändert sich online nichts. Das schwarze Fenster, das beim Start aufgeht, bleibt offen, solange man arbeitet.

Hochgeladene Originale bleiben zusätzlich in `originals/` auf dem Rechner liegen (nicht online).
Bearbeiten lassen sich die elf Galerien. Startseite, Vita, Events, Press und Contact noch nicht.

Zum Ausprobieren ohne Hochladen: `python3 admin/server.py --no-push` (Leiste ist dann braun).

### Einrichtung auf einem neuen Mac (einmalig)

1. Terminal öffnen, `xcode-select --install` eingeben, den Dialog bestätigen. Das bringt Python und Git mit.
2. Projektordner auf den Rechner holen (`git clone …`).
3. GitHub-Zugang hinterlegen: beim ersten „Veröffentlichen" fragt Git nach Benutzername und Zugangsschlüssel und merkt sie sich im Schlüsselbund.
4. Beim ersten Doppelklick auf die `.command`-Datei fragt macOS nach: Rechtsklick → „Öffnen" → „Öffnen".

Online gebaut wird durch `.github/workflows/pages.yml`: Jeder Stand auf `main` wird veröffentlicht, Quelle ist der Ordner `site/`.

Statische Seite ohne Framework. Der Ordner `site/` ist die fertige Website und kann so auf GitHub Pages.

## Ansehen

```
cd site
python3 -m http.server 8010
```

Dann http://localhost:8010 öffnen. Nicht per Doppelklick auf die HTML-Datei, sonst lädt das YouTube-Video nicht.

## Aufbau

| Ordner / Datei | Inhalt |
|---|---|
| `data/<seite>.json` | Pro Seite: Bilder (Datei, Titel, Angaben, Maße) und Textblöcke |
| `data/layout.json` | Abstände, Raster-Art und Positionen pro Seite, am Wix-Original ausgemessen |
| `templates/base.html` | Grundgerüst jeder Seite (Kopf, Menü, Fuß) |
| `build.py` | Erzeugt aus `data/` und `templates/` die HTML-Dateien in `site/` |
| `site/css/style.css`, `site/js/gallery.js` | Aussehen, Raster, Großansicht, Menü |
| `site/img/<seite>/thumb` und `/large` | Bilder, lange Kante 800px und 2000px |
| `admin/` | Die Bearbeitungs-App: `server.py` (lokaler Server), `edit.js`, `edit.css` |
| `Website bearbeiten.command` | Starter per Doppelklick |
| `tools/scrape.py` | Einmaliger Abzug von Wix. Wird nach dem Umzug nicht mehr gebraucht |

Nach jeder Änderung in `data/` oder `templates/`: `python3 build.py`.
Nach Änderungen an CSS oder JS: `ASSET_VERSION` in `build.py` hochzählen und neu bauen, sonst zeigt der Browser die alte Datei.

## Ein Bild hinzufügen

1. Bild in zwei Größen ablegen: `site/img/painting/thumb/35-titel.jpg` (lange Kante 800px) und `site/img/painting/large/35-titel.jpg` (2000px).
2. In `data/painting.json` unter `items` einen Eintrag ergänzen:
   ```json
   {"file": "35-titel.jpg", "title": "TITEL", "description": "100 x 80cm\noil on canvas\n2026", "alt": "", "width": 2000, "height": 1600}
   ```
   `width` und `height` sind die Pixelmaße der großen Datei. Die Reihenfolge in der Liste ist die Reihenfolge auf der Seite.
3. `python3 build.py`

## Raster-Arten (`data/layout.json`, Feld `type`)

- `rows`: Zeilen gleicher Höhe, wie bei Wix. Neue Bilder ordnen sich von selbst ein.
- `columns`: Spalten gleicher Breite (BODY, OBJECT).
- `grid`: Zwei Spalten mit quadratischen Feldern (Startseite).
- `fixed`: Collage mit festen, ausgemessenen Kästen (COMERCIAL). Zusätzliche Bilder hängen als Zeilen darunter.

## Abweichungen vom Original

- **Schrift.** Wix nutzt DIN Next Light (Lizenzschrift, darf nicht mitgenommen werden). Hier: Barlow Light, frei (OFL, `site/fonts/OFL.txt`). Sie läuft etwas breiter; lange Textblöcke brechen deshalb stellenweise anders um.
- **Großansicht.** Ohne Wix' Herz-, Teilen- und Vollbild-Knöpfe. Bildadresse ist `…/painting/#01-ella-and-sarah` statt `?pgid=…`.
- **Seitentitel.** „PAINTING | Nicolas Schützinger" statt „PAINTING | My Site".
- **Video.** Über `youtube-nocookie.com` eingebunden.
- **Bilder.** Alle als JPEG, auch die sieben PNG-Quellen (keine hatte Transparenz).
- **Titel auf der Startseite.** Am Handy sichtbar wie im Original. Am Desktop erscheinen sie beim Überfahren; das Verhalten dort ist angenommen, nicht gemessen.

## Vor einer Veröffentlichung

- `noindex` in `templates/base.html` entfernen.
- Impressum und Datenschutzerklärung ergänzen. Die jetzige Seite hat nur englische „terms & conditions" aus der Wix-Vorlage.
- Tippfehler aus dem Original, unverändert übernommen: „COMERCIAL" im Menü, die Adresse `/projects-7` für OBJECT, `/kontakt-1` für CONTACT.
- Die Events-Seite nennt als aktuelle Ausstellung „Blüten tragen" (bis 29.02.2024).
- Domain bei Wix lösen und auf GitHub Pages zeigen lassen; Datei `CNAME` in `site/` anlegen.
