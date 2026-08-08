# AUTO ΤΖΗΜΑΓΙΩΡΓΗΣ — Website (Anleitung, Deutsch)

**Live:** https://www.auto-tzimagiorgis.com
**Code:** https://github.com/dimi2404/auto-tzimagiorgis (GitHub Pages, Branch `main`)

Statische Website, kein Backend, keine Datenbank. Reines HTML/CSS/JS —
gehostet über GitHub Pages, Veröffentlichung per `git push`.

Aktueller Stand: **33 Fahrzeuge**, **1.193 Fotos** im WebP-Format, ca. **96 MB**.

Jedes Fahrzeug hat eine **eigene Seite** unter `cars/<id>.html` — mit eigenem Google-Eintrag
und Vorschaubild beim Teilen per WhatsApp/Facebook.

## 1. Struktur

```
index.html            Startseite (Hero, Marken, Fahrzeug-Grid, Über uns, Kontakt)
cars/<id>.html        Je eine fertige Seite pro Fahrzeug (vom Skript erzeugt)
legal.html            Στοιχεία επιχείρησης / Impressum
privacy.html          Πολιτική απορρήτου / Datenschutz
404.html              Fehlerseite
assets/css/main.css   Design (Farben ganz oben als CSS-Variablen)
assets/js/gallery.js  Fotogalerie der Detailseite (Pfeile, Thumbnails, Lightbox)
assets/js/cars.js     Startseite: Grid, Filter, Sortierung
assets/js/detail.js   Detailseite: hängt die Galerie an (Inhalt steht im HTML)
assets/js/legal.js    Rechtliche Seiten
assets/js/site.js     Gemeinsame Helfer (Kontaktdaten einsetzen, Animationen)
data/cars.json        ALLE Fahrzeuge — wird vom Import-Skript erzeugt
data/site.json        Kontaktdaten, Öffnungszeiten, Texte  ← hier von Hand pflegen
images/cars/<id>/     Fotos pro Fahrzeug
images/brands/        Markenlogos (Platzhalter, s. Punkt 5)
tools/                Skripte — NICHT auf den Server hochladen
```

## 2. Fahrzeuge aktualisieren (der Normalfall)

Die Fahrzeuge kommen automatisch von car.gr (`tzimagiorgis.car.gr`). Wenn der Kunde
dort ein Auto einstellt, ändert oder verkauft, im Projektordner einfach ausführen:

```bash
python3 tools/import-cargr.py
```

Das Skript

1. liest alle Inserate von `/cars/` **und** `/vans/`,
2. schreibt `data/cars.json` komplett neu (Preise, km, Specs, Ausstattung auf Griechisch),
3. lädt fehlende Fotos nach `images/cars/<id>/` (bereits vorhandene werden übersprungen),
4. erzeugt `sitemap.xml`,
5. erzeugt die 34 Fahrzeugseiten unter `cars/`,
6. benennt Bildordner um, falls sich ein Fahrzeugname geändert hat,
7. entfernt doppelte Anzeigen (Fahrzeuge, die auf car.gr unter PKW *und*
   Nutzfahrzeuge stehen).

Danach `data/`, `images/`, `cars/` und `sitemap.xml` erneut hochladen — fertig.

Nur Daten, ohne Fotos (schnell):

```bash
python3 tools/import-cargr.py --no-images
```

Sitemap mit der echten Domain erzeugen:

```bash
SITE_URL=https://www.deine-domain.gr python3 tools/import-cargr.py --no-images
```

**Verkaufte Autos**: verschwinden beim nächsten Import automatisch, sobald das Inserat
auf car.gr weg ist. Die Bilderordner bleiben liegen und können gelöscht werden.

### Fotogrößen

Pro Foto werden bis zu drei Varianten geladen:

| Datei              | Größe   | wofür                                           |
|--------------------|---------|-------------------------------------------------|
| `000_thumb.webp`   | 320 px  | Thumbnail-Leiste der Galerie                    |
| `000.webp`         | 575 px  | Titelbild der Karte und großes Galeriebild      |
| `000_large.webp`   | 1024 px | Großansicht / Lightbox (erste 10 Fotos je Auto) |

Die Fotos werden als JPG von car.gr geladen und danach in WebP umgewandelt
(ca. 35 % kleiner bei gleicher Qualität):

```bash
python3 tools/optimize-images.py
python3 tools/import-cargr.py --no-images   # schreibt die neuen Pfade
```

Das hält die Startseite schnell: pro Fahrzeug wird dort nur **ein** Titelbild geladen,
und zwar erst, wenn die Karte in den sichtbaren Bereich scrollt.

## 2a. Ein Fahrzeug ausblenden

Soll ein Auto nicht auf der Website erscheinen (obwohl es auf car.gr steht), die
car.gr-ID in `data/excluded.json` eintragen. Die ID steht am Ende der Adresse:
`tzimagiorgis.car.gr/cars/view/`**`49439267`**

```json
{ "id": 49439267, "grund": "LKW, soll nicht auf die Website" }
```

Danach `python3 tools/import-cargr.py --no-images` — das Fahrzeug wird bei jedem
weiteren Import übersprungen. Den zugehörigen Ordner unter `images/cars/` kann
man löschen.

## 3. Fahrzeug von Hand ändern

Alles steht in `data/cars.json`. Achtung: beim nächsten Import wird die Datei
überschrieben. Dauerhafte manuelle Änderungen also entweder direkt auf car.gr machen
oder nach jedem Import erneut eintragen.

Nützliche Felder: `status` (`"available"` / `"reserved"` → Badge „ΚΡΑΤΗΜΕΝΟ"),
`vehicleType` (`Επιβατικά` / `Επαγγελματικά`), `crashed`, `priceWithoutVat`.

## 4. Kontaktdaten / Texte ändern

`data/site.json` — Telefon, Mobil, FAX, Email, Adresse, Öffnungszeiten, Über-uns-Text
und die vier Vertrauens-Punkte. Wird automatisch in Header, Kontaktbereich und
Detailseiten eingesetzt. Leere Felder (z. B. FAX) werden auf der Seite ausgeblendet.

## 5. Markenlogos

`images/brands/*.svg` sind aktuell **Platzhalter** (nur Schriftzüge). Echte Logos als
SVG oder PNG mit demselben Dateinamen ersetzen — hell, auf transparentem Hintergrund.
Vorhanden: ford, mercedes-benz, opel, fiat, toyota, mitsubishi, peugeot, renault, suzuki.

## 6. Farben / Design

Ganz oben in `assets/css/main.css`:

```css
--red:  #ae252b;   /* Hauptfarbe laut Vorlage */
--black:#000000;
```

## 7. Lokal testen

Wegen `fetch()` und ES-Modulen funktioniert ein Doppelklick auf `index.html` **nicht**.
Im Projektordner:

```bash
python3 tools/serve.py
```

Dann <http://localhost:4321> öffnen.

## 8. Änderungen veröffentlichen

Die Seite liegt bei GitHub und wird von GitHub Pages ausgeliefert. Kein FTP nötig —
ein Push genügt, ein bis zwei Minuten später ist die Änderung live:

```bash
cd /Users/dimi/Desktop/Business/autohaus-website
git add -A
git commit -m "Fahrzeugbestand aktualisiert"
git push
```

Kompletter Ablauf, wenn neue Autos auf car.gr stehen:

```bash
python3 tools/import-cargr.py
SITE_URL=https://www.auto-tzimagiorgis.com python3 tools/build_pages.py
git add -A && git commit -m "Fahrzeugbestand aktualisiert" && git push
```

Den Stand der Veröffentlichung siehst du mit:

```bash
gh api repos/dimi2404/auto-tzimagiorgis/pages/builds/latest --jq .status
```

**Wichtig:** Die Datei `CNAME` im Hauptordner enthält die Domain. Sie darf nicht
gelöscht werden — sonst verliert GitHub Pages die Verknüpfung zur Domain.

## 8a. Rechtliche Angaben ergänzen (Pflicht vor dem Launch)

In `data/site.json` unter `"legal"` eintragen: `owner` (Name des Verantwortlichen),
`vat` (ΑΦΜ), `taxOffice` (ΔΟΥ), `gemi` (Αρ. ΓΕΜΗ). Leere Felder werden auf
`legal.html` automatisch ausgeblendet — solange sie leer sind, ist die Seite
unvollständig und die Website nicht rechtssicher.

## 9. Domain / DNS (erledigt)

Domain bei Namecheap, Auslieferung über GitHub Pages. Eingetragen sind:

| Typ   | Host | Wert                  |
|-------|------|-----------------------|
| A     | `@`  | `185.199.108.153`     |
| A     | `@`  | `185.199.109.153`     |
| A     | `@`  | `185.199.110.153`     |
| A     | `@`  | `185.199.111.153`     |
| CNAME | `www`| `dimi2404.github.io.` |

`auto-tzimagiorgis.com` (ohne www) und alle HTTP-Aufrufe leiten auf
`https://www.auto-tzimagiorgis.com` um. HTTPS ist erzwungen, das Zertifikat
erneuert GitHub automatisch.

## 10. Hinweis zu den Fotos

Die Fotos stammen aus den eigenen car.gr-Inseraten des Händlers. Auf der Startseite
zeigt jede Karte das **erste** Foto des Inserats als Titelbild — auf car.gr also einfach
das gewünschte Titelfoto an die erste Stelle ziehen.

**360°-Ansicht (später):** Die Drehplattform ist vorerst ausgebaut. Für eine echte
360°-Ansicht braucht jedes Auto eine gleichmäßige Rundum-Fotoserie: in gleichen
Schritten einmal komplett um das Auto herum (18–36 Fotos), gleicher Abstand und
gleiche Höhe, erst danach Innenraum- und Detailaufnahmen. Sobald solche Serien
vorliegen, kann die Funktion wieder eingebaut werden.
