# Projekt: Website Auto Τζημαγιώργης

Kundenauftrag von Dimi. Griechischer Autohändler in Katerini, importiert Autos aus
Deutschland. Website komplett auf Griechisch. Auftragswert 900–1000 €.

- **Live:** https://www.auto-tzimagiorgis.com
- **Code:** https://github.com/dimi2404/auto-tzimagiorgis — GitHub Pages, Branch `main`
- **Quelle der Fahrzeuge:** https://tzimagiorgis.car.gr (PKW unter `/cars/`, Nutzfahrzeuge unter `/vans/`)

## Stand

33 Fahrzeuge (25 PKW, 8 Nutzfahrzeuge), 1.193 Fotos, 97 MB. Statische Seite,
kein Framework, kein Build-Schritt, keine Abhängigkeiten. Sprache: Griechisch.
Kommunikation mit Dimi: **Deutsch**.

## Wie es gebaut ist

```
index.html            Startseite
cars/<id>.html        33 Fahrzeugseiten — erzeugt, nie von Hand bearbeiten
legal.html            Στοιχεία επιχείρησης
privacy.html          Πολιτική απορρήτου
assets/css/main.css   gesamtes Design, Farben als Variablen oben
assets/js/            cars.js (Startseite), gallery.js, detail.js, site.js, legal.js
tools/                Python-Skripte, laufen nur lokal
data/site.json        Kontaktdaten und Texte — hier pflegen
data/cars.json        erzeugt vom Import
data/excluded.json    car.gr-IDs, die nicht auf die Seite sollen
```

## Bestand aktualisieren

```bash
python3 tools/import-cargr.py
SITE_URL=https://www.auto-tzimagiorgis.com python3 tools/build_pages.py
git add -A && git commit -m "Fahrzeugbestand aktualisiert" && git push
```

`build_pages.py` **immer mit SITE_URL** aufrufen — sonst fehlen canonical, og:url
und og:image, und WhatsApp zeigt beim Teilen kein Vorschaubild.

Neue Fotos danach einmal umwandeln: `python3 tools/optimize-images.py`
(JPG → WebP, spart rund 35 %).

Lokal ansehen: `python3 tools/serve.py` → http://localhost:4321

## Wichtig zu wissen

- **car.gr drosselt** bei zu vielen Anfragen (HTTP 429). Dann warten, nicht neu starten.
- **`CNAME` im Hauptordner** enthält die Domain. Löschen bricht die Verknüpfung.
- **Öffnungszeiten** stehen in `data/site.json`, nicht im HTML.
- **Logo:** `images/logo-jk-hell.png` (helles J) sitzt im Header auf dunklem Grund.
  `images/logo-jk.png` ist das Original mit schwarzem J für helle Untergründe.
- Die **360°-Drehplattform wurde ausgebaut** (Wunsch des Kunden, kommt evtl. später
  zurück). Dafür bräuchte jedes Auto eine gleichmäßige Rundum-Fotoserie, 18–36 Bilder.
- **Viber wurde entfernt** — nur WhatsApp, Telefon und Email.

## Noch offen

1. **ΑΦΜ, ΔΟΥ, Αρ. ΓΕΜΗ, Name des Verantwortlichen** — in `data/site.json` unter
   `legal` eintragen. Leere Felder blenden sich auf `legal.html` automatisch aus.
   Solange sie fehlen, ist die Seite nicht rechtssicher.
2. **Öffnungszeiten bestätigen** — aktuell geraten: Mo–Fr 9–19, Sa 9–15, So zu.
3. **Fax** — steht auf der Festnetznummer. Prüfen, ob dort wirklich ein Gerät hängt.
4. **Original-Logodatei** vom Schildermacher, falls erhältlich (Vektor).
5. **Markenlogos** im Hero sind die echten von Wikimedia; Fiat und Opel wurden
   auf Weiß umgefärbt, weil sie schwarz auf dunklem Grund unsichtbar waren.
