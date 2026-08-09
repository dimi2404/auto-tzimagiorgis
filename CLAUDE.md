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

## Überwachung

`tools/watch-site.py` prüft die Live-Seite alle 5 Minuten: DNS (CNAME + die vier
GitHub-Pages-IPs, Nameserver), TLS-Ablauf, sieben Pflichtseiten mit Inhaltsprobe,
und aus `cars.json` je Lauf eine rotierende Fahrzeugseite samt Foto.

```bash
python3 tools/watch-site.py             # einmal prüfen
python3 tools/watch-site.py --verbose   # alle Einzelergebnisse
python3 tools/watch-site.py --status    # letzter Stand + Historie
python3 tools/watch-site.py --install   # als launchd-Dienst einrichten
python3 tools/watch-site.py --uninstall
```

- Alarm per macOS-Mitteilung, nur bei **Zustandswechsel**, danach höchstens alle
  6 Stunden. Optional zusätzlich ein Webhook über `WATCHER_WEBHOOK`.
- Jeder Lauf schreibt `Auto Tzimagiorgis/Website-Status.md` in den Obsidian-Vault
  (Pfad überschreibbar mit `WATCHER_VAULT`) — dort liest ein Agent den Stand nach.
- Zustand, Log und die vom Dienst ausgeführte Skriptkopie liegen in
  `~/Library/Application Support/auto-tzimagiorgis-watcher/`. **Nicht** im
  Projektordner, weil launchd `~/Desktop` nicht lesen darf (macOS-Dateischutz).
- Nach jeder Änderung an `watch-site.py` einmal `--install` aufrufen, sonst läuft
  der Dienst mit der alten Kopie weiter.

### Rund um die Uhr, ohne Kosten

`.github/workflows/watch-site.yml` fährt dieselben Prüfungen alle 10 Minuten auf
GitHub-Rechnern — läuft also auch, wenn der Mac aus ist. Das Repo ist öffentlich,
damit sind die Actions-Minuten unbegrenzt und gratis.

- Bei Störung legt der Workflow ein Issue mit Label `website-down` an. Bleibt die
  Störung, bleibt das Issue offen — kein Kommentar alle 10 Minuten. Sobald die
  Seite wieder läuft, wird kommentiert und geschlossen.
- Benachrichtigung kommt über GitHub (Mail und GitHub-App aufs Handy), weil man
  eigene Repos automatisch beobachtet.
- Der Modus dazu ist `python3 tools/watch-site.py --ci`: keine macOS-Mitteilung,
  keine Obsidian-Notiz, kein Zustandsspeicher, Bericht nach `ci-report.md`.
- GitHub kann geplante Läufe bei Last **verzögern**, mal 10, mal 25 Minuten. Für
  Sofortmeldungen ist der lokale launchd-Dienst da; die Action ist das Netz darunter.
- Geplante Workflows werden von GitHub nach **60 Tagen ohne Commit** abgeschaltet.
  Da regelmäßig Fahrzeugbestand gepusht wird, passiert das im Normalfall nicht.

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
