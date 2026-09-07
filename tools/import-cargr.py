#!/usr/bin/env python3
"""Importiert alle Fahrzeuge des Haendlers von car.gr in data/cars.json
und laedt alle Fotos nach images/cars/<id>/ herunter.

Aufruf:
    python3 tools/import-cargr.py            # Daten + Bilder
    python3 tools/import-cargr.py --no-images  # nur Daten aktualisieren

Bildgroessen von car.gr: v(134px) n(320px) m(460px) z(575px) b(1024px)
- PHOTO_SIZE = Galerie, Thumbnails und Titelbild (alle Fotos)
- LARGE_SIZE = Grossansicht/Lightbox (nur die ersten LARGE_COUNT Fotos)
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from html.parser import HTMLParser

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = "https://tzimagiorgis.car.gr"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0 Safari/537.36")
THUMB_SIZE = "n"   # Thumbnail-Leiste (320 px)
PHOTO_SIZE = "z"   # Galerie + Titelbild (575 px)
LARGE_SIZE = "b"   # Lightbox / Grossansicht (1024 px)
LARGE_COUNT = 10   # so viele Fotos je Fahrzeug zusaetzlich in gross
# (Fahrzeugtyp, Uebersichtsseite) — car.gr trennt PKW und Nutzfahrzeuge
# Abstand zwischen zwei Detailseiten. car.gr drosselt haerter als frueher:
# unter ~4 s kommen nach ein paar Dutzend Abrufen nur noch 429er. Der komplette
# Bestand braucht damit rund vier Minuten - das ist der Preis dafuer, nicht
# gesperrt zu werden. Ueber CARGR_DELAY anpassbar.
PAGE_DELAY = float(os.environ.get("CARGR_DELAY", "4"))
CACHE_DIR = os.path.join(ROOT, ".cache", "cargr")
LIST_PAGES = [
    ("Επιβατικά", "/cars/"),
    ("Επιβατικά", "/cars/?pg=2"),
    ("Επιβατικά", "/cars/?pg=3"),
    ("Επαγγελματικά", "/vans/"),
    ("Επαγγελματικά", "/vans/?pg=2"),
]


def get(url, binary=False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=60) as res:
        data = res.read()
    return data if binary else data.decode("utf-8", "replace")


def excluded_ids():
    """IDs aus data/excluded.json — diese Fahrzeuge werden nie importiert."""
    path = os.path.join(ROOT, "data", "excluded.json")
    if not os.path.exists(path):
        return set()
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    return {str(entry["id"]) for entry in data.get("ids", [])}


def find_ids():
    """[(id, Fahrzeugtyp)] ueber alle Uebersichtsseiten, ohne Duplikate."""
    found = []
    seen = set(excluded_ids())
    if seen:
        print(f"{len(seen)} Fahrzeug(e) laut data/excluded.json ausgeschlossen.")
    for vehicle_type, page in LIST_PAGES:
        try:
            html = get(BASE + page)
        except Exception:
            continue
        new = [i for i in re.findall(r"/(?:cars|vans)/view/(\d+)", html) if i not in seen]
        for cid in new:
            seen.add(cid)
            found.append((cid, vehicle_type))
    return found


def spec_map(classified):
    out = {}
    for spec in classified.get("specifications") or []:
        value = spec.get("value")
        if isinstance(value, str):
            out[spec["name"]] = value
    return out


def num(text):
    """'32.957 χλμ' -> 32957 ; '1.000 cc' -> 1000"""
    if not text:
        return None
    digits = re.sub(r"[^\d]", "", text.split(",")[0])
    return int(digits) if digits else None


def slugify(text):
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


def description_text(value):
    """car.gr liefert die Beschreibung mal als String, mal als Objekt."""
    if isinstance(value, str):
        text = value
    elif isinstance(value, dict):
        text = value.get("text") or value.get("value") or value.get("raw") or ""
        if not isinstance(text, str):
            text = ""
    else:
        text = ""
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


TYPO_FIXES = {
    "disel": "Diesel",
    "spinter": "Sprinter",
    "patner": "Partner",
    "automatik": "Automatic",
    "klima": "Klima",
    "turer": "Tourer",
}


def clean_variant(variant, make, model):
    """Die Variante kommt frei getippt vom Haendler: 'COURIER CD', 'OPEL COMBO
    1.6 DISEL MAXI'. Hier wird sie lesbar gemacht: Marke/Modell nicht doppeln,
    SCHREIEN in Normalschrift, bekannte Tippfehler korrigieren."""
    if not variant:
        return ""
    drop = {w.lower() for w in (make + " " + model).split()}
    words = []
    for raw in variant.split():
        # Satzzeichen abtrennen, sonst greift die Korrektur bei 'TRANSIT.' nicht
        word = raw.strip(".,/-")
        if not word:
            continue
        low = word.lower()
        if low in drop:          # 'Courier COURIER CD' -> 'CD'
            continue
        if low in TYPO_FIXES:
            fixed = TYPO_FIXES[low]
            if fixed.lower() in drop:   # 'Sprinter 313 SPINTER' -> '313'
                continue
            words.append(fixed)
        elif word.isupper() and len(word) > 3 and word.isalpha():
            words.append(word.capitalize())   # 'MAXI' -> 'Maxi'
        else:
            words.append(word)
    return " ".join(words).strip(" .-")


# ----------------------------------------------------------------------------
# car.gr hat die JSON-API im Sommer 2026 hinter eine Cloudflare-Pruefung gelegt:
# /api/classifieds/<id>/ antwortet nur noch mit 403. Die oeffentlichen
# Detailseiten sind weiter frei zugaenglich und enthalten dieselben Angaben im
# HTML. Der Importer liest sie deshalb von dort und baut daraus genau die
# Struktur nach, die frueher die API lieferte — build_car() bleibt unveraendert.
# ----------------------------------------------------------------------------

VOID_TAGS = {"br", "img", "input", "meta", "link", "hr", "source", "path",
             "circle", "use", "col", "area", "base", "embed", "track", "wbr"}


class Node(object):
    __slots__ = ("tag", "attrs", "kids", "parent", "text")

    def __init__(self, tag="", attrs=None, parent=None):
        self.tag = tag
        self.attrs = attrs or {}
        self.kids = []
        self.parent = parent
        self.text = ""

    @property
    def cls(self):
        return self.attrs.get("class", "")

    def all_text(self):
        parts = [self.text]
        for kid in self.kids:
            parts.append(kid.all_text())
        return " ".join(p for p in parts if p).strip()


class _Tree(HTMLParser):
    """Winziger DOM-Aufbau. Reicht fuer car.gr und braucht keine Fremdpakete."""

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.root = Node("#root")
        self.cur = self.root

    def handle_starttag(self, tag, attrs):
        node = Node(tag, dict(attrs), self.cur)
        self.cur.kids.append(node)
        if tag not in VOID_TAGS:
            self.cur = node

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, dict(attrs), self.cur))

    def handle_endtag(self, tag):
        if tag in VOID_TAGS:
            return
        node = self.cur
        while node is not self.root and node.tag != tag:
            node = node.parent
        if node is not self.root and node.parent is not None:
            self.cur = node.parent

    def handle_data(self, data):
        text = data.strip()
        if text:
            self.cur.text = (self.cur.text + " " + text).strip()


def parse_html(markup):
    tree = _Tree()
    tree.feed(markup)
    return tree.root


def walk(node):
    yield node
    for kid in node.kids:
        for inner in walk(kid):
            yield inner


def json_ld_vehicle(markup):
    """Der Fahrzeug-Block aus den JSON-LD-Daten der Seite (Name, Fotos, Preis)."""
    for block in re.findall(
            r'<script type="application/ld\+json"[^>]*>(.*?)</script>', markup, re.S):
        try:
            data = json.loads(block)
        except ValueError:
            continue
        if isinstance(data, dict) and (data.get("vehicleTransmission")
                                       or data.get("mileageFromOdometer")
                                       or data.get("vehicleEngine")):
            return data
    return {}


# car.gr beschriftet die Merkmale griechisch. Links die Beschriftung auf der
# Seite, rechts der Name, den build_car() erwartet.
SPEC_LABELS = {
    "Χρονολογία": "registration",
    "Τιμή": "price",
    "Χιλιόμετρα": "mileage",
    "Καύσιμο": "fuel_type",
    "Σασμάν": "gearbox_type",
    "Ιπποδύναμη": "engine_power",
    "Κυβικά": "engine_size",
    "Πόρτες": "doors",
    "Θέσεις επιβατών": "seats",
    "Χρώμα": "exterior_color",
    "Χρώμα εσωτερικού": "interior_color",
    "Επένδυση σαλονιού": "interior_type",
    "Κίνηση τροχών": "drive_type",
    "Κλάση ρύπων": "euroclass",
    "Εκπομπές CO2": "emissions_co2",
    "ΚΤΕΟ μέχρι": "kteo",
    "Τέλη κυκλοφορίας": "circulation_tax",
    "Σύνολο κατόχων": "previous_owners",
    "Αερόσακοι": "airbags",
    "Μέγεθος ζάντας": "rim_size",
    "Κατάσταση": "condition",
}
BRAND_LABEL = "Μάρκα - μοντέλο"
VARIANT_LABEL = "Τύπος / έκδοση"
EXTRAS_HEADING = "Ιδιαιτερότητες"
DESCRIPTION_HEADING = "Περιγραφή"


def label_pairs(root):
    """Alle Merkmalzeilen der Seite als (Beschriftung, Wert)."""
    pairs = []
    for node in walk(root):
        if "tw-grid-cols-2" not in node.cls:
            continue
        kids = [k for k in node.kids if k.tag not in ("#text",)]
        if len(kids) < 2 or "tw-font-medium" not in kids[0].cls:
            continue      # ohne fette Beschriftung ist es die Ausstattungsliste
        key = kids[0].all_text()
        value = kids[1].all_text()
        if key:
            pairs.append((key, value))
    return pairs


def extras_list(root):
    """Ausstattung unter der Ueberschrift 'Ιδιαιτερότητες'."""
    for node in walk(root):
        if node.all_text().strip() == EXTRAS_HEADING and node.parent is not None:
            block = node.parent
            items = []
            for inner in walk(block):
                if "tw-grid-cols-2" not in inner.cls:
                    continue
                for cell in inner.kids:
                    text = cell.all_text().strip()
                    if text and text not in items:
                        items.append(text)
            if items:
                return items
    return []


def description_from(root):
    for node in walk(root):
        if node.all_text().strip().startswith(DESCRIPTION_HEADING) and node.parent:
            text = node.parent.all_text()
            return text.replace(DESCRIPTION_HEADING, "", 1).strip()
    return ""


# car.gr nummeriert die Fotos einstellig: 0-9, dann a-z, dann A-Z.
# Gross- und Kleinschreibung sind verschiedene Bilder ('d' ist nicht 'D'),
# darum eine eigene Reihenfolge statt int(..., 36).
PHOTO_INDEX = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"


def photo_patterns(markup, cid, vehicle):
    """Foto-URLs als Muster mit {size}, so wie sie die API geliefert hat.

    Zwei Quellen, weil keine allein vollstaendig ist: die JSON-LD-Daten listen
    alle Fotos, fehlen aber bei manchen Inseraten ganz; im Markup stehen nur
    die ersten (der Rest wird nachgeladen), dafuer immer.
    """
    found = []
    for url in (vehicle.get("image") or []):
        if isinstance(url, str):
            found += re.findall(r"static\.car\.gr/%s_(.)_[a-z]\.jpg" % cid, url)
    found += re.findall(r"static\.car\.gr/%s_(.)_[a-z]\.jpg" % cid, markup)

    seen = []
    for index in found:
        if index in PHOTO_INDEX and index not in seen:
            seen.append(index)
    seen.sort(key=PHOTO_INDEX.index)
    return [{"url": "https://static.car.gr/%s_%s_{size}.jpg" % (cid, i)} for i in seen]


def classified_from_html(cid, markup):
    """Baut aus der Detailseite die Struktur nach, die build_car() erwartet."""
    vehicle = json_ld_vehicle(markup)
    body = re.sub(r"<script.*?</script>|<style.*?</style>", "", markup, flags=re.S)
    root = parse_html(body)

    pairs = label_pairs(root)
    specs, make_model, variant = {}, "", ""
    for key, value in pairs:
        if key == BRAND_LABEL:
            make_model = make_model or value
        elif key == VARIANT_LABEL:
            variant = variant or value
        elif key in SPEC_LABELS and value:
            specs.setdefault(SPEC_LABELS[key], value)

    make, _, model = make_model.partition(" ")
    name = vehicle.get("name") or ""
    if not name:
        match = re.search(r"<h1[^>]*>(.*?)</h1>", markup, re.S) or \
                re.search(r"<title>(?:Car\.gr\s*-\s*)?(.*?)</title>", markup, re.S)
        if match:
            name = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", match.group(1))).strip()
    year = num((specs.get("registration") or "").split("/")[-1])
    if not year:
        year = num(str(vehicle.get("modelDate") or vehicle.get("productionDate") or ""))
    if not variant:
        # Was im Titel uebrig bleibt, wenn Marke, Modell und Baujahr weg sind.
        rest = name
        for word in (make_model.split() + [str(year or "")]):
            if word:
                rest = re.sub(r"(?<!\w)%s(?!\w)" % re.escape(word), " ", rest)
        variant = " ".join(rest.split())

    extras = extras_list(root)
    price_raw = None
    offers = vehicle.get("offers") or {}
    if isinstance(offers, list):
        offers = offers[0] if offers else {}
    if isinstance(offers, dict):
        try:
            price_raw = int(float(offers.get("price")))
        except (TypeError, ValueError):
            price_raw = None

    return {
        "title_parts": {"make": make, "model": model, "variant": variant, "year": year},
        "specifications": [{"name": k, "value": v} for k, v in specs.items()],
        "photos_compact": {"native": {"photos": photo_patterns(markup, cid, vehicle)}},
        "price": {"extra": {"rawPrice": price_raw,
                            "without_vat": "χωρίς ΦΠΑ" in markup or "Χωρίς ΦΠΑ" in markup}},
        "key_features": [{"key": "category", "value": specs.get("category")
                          or dict(pairs).get("Κατηγορία")}],
        "extras": [{"value": e} for e in extras],
        "description": description_from(root),
        "crashed": any("Τρακαρισμ" in e for e in extras),
    }


def cached_page(cid):
    """Zuletzt geholte Detailseite, sofern noch frisch genug.

    car.gr sperrt Detailseiten schnell. Der Cache erlaubt es, den Import kurz
    hintereinander laufen zu lassen (Probelauf, dann echter Lauf) ohne die
    Seiten erneut abzurufen. CARGR_CACHE_MINUTES=0 schaltet ihn ab."""
    minutes = float(os.environ.get("CARGR_CACHE_MINUTES", "60"))
    if minutes <= 0:
        return None
    path = os.path.join(CACHE_DIR, "%s.html" % cid)
    if not os.path.exists(path) or os.path.getsize(path) < 50000:
        return None
    if (time.time() - os.path.getmtime(path)) > minutes * 60:
        return None
    with open(path, encoding="utf-8", errors="replace") as fh:
        return fh.read()


def store_page(cid, markup):
    try:
        os.makedirs(CACHE_DIR, exist_ok=True)
        with open(os.path.join(CACHE_DIR, "%s.html" % cid), "w", encoding="utf-8") as fh:
            fh.write(markup)
    except OSError:
        pass          # Cache ist Beiwerk, ein Fehler darf den Import nicht kippen


def fetch_classified(cid, vehicle_type):
    """Detailseite holen. car.gr drosselt (429) — dann warten statt aufgeben."""
    hit = cached_page(cid)
    if hit is not None:
        return classified_from_html(cid, hit)
    section = "vans" if vehicle_type.startswith("Επαγγ") else "cars"
    url = "%s/%s/view/%s/" % (BASE, section, cid)
    delay = 60
    for attempt in range(5):
        try:
            markup = get(url)
            store_page(cid, markup)
            return classified_from_html(cid, markup)
        except urllib.error.HTTPError as error:
            # 410/404 = verkauft und geloescht, das Fahrzeug faellt zu Recht raus.
            # 429 und 5xx sind voruebergehend - da lohnt ein zweiter Versuch.
            if error.code in (404, 410) or attempt == 4:
                raise
            if error.code != 429 and error.code < 500:
                raise
            print("    429 von car.gr — %d s warten" % delay)
            time.sleep(delay)
            delay = min(delay * 2, 600)
    raise RuntimeError("unerreichbar: %s" % url)


def build_car(cid, payload):
    c = payload["data"]["classified"]
    parts = c.get("title_parts") or {}
    specs = spec_map(c)

    make = parts.get("make") or ""
    model = parts.get("model") or ""
    variant = clean_variant((parts.get("variant") or "").strip(), make, model)
    if not model:
        # Nutzfahrzeuge kommen ohne Modell — dann traegt die Variante den Namen
        model, variant = variant, ""
    year = parts.get("year") or num(specs.get("registration", "").split("/")[-1])

    photos = ((c.get("photos_compact") or {}).get("native") or {}).get("photos") or []
    slug = slugify(f"{make}-{model}-{variant or year}-{cid}")

    def photo_path(name):
        """WebP bevorzugen, sofern tools/optimize-images.py schon gelaufen ist."""
        rel = f"images/cars/{slug}/{name}"
        webp = rel[:-4] + ".webp"
        return webp if os.path.exists(os.path.join(ROOT, webp)) else rel

    images, images_large, images_thumb = [], [], []
    for i, photo in enumerate(photos):
        images.append(photo_path(f"{i:03d}.jpg"))
        images_thumb.append(photo_path(f"{i:03d}_thumb.jpg"))
        if i < LARGE_COUNT:
            images_large.append(photo_path(f"{i:03d}_large.jpg"))

    car = {
        "id": slug,
        "carGrId": int(cid),
        "brand": make,
        "model": model,
        "modelFull": (model + (" " + variant if variant else "")).strip(),
        "variant": variant,
        "year": year,
        "registration": specs.get("registration"),
        "price": (c.get("price") or {}).get("extra", {}).get("rawPrice")
                 or (c.get("price") or {}).get("extra", {}).get("raw_price")
                 or num(specs.get("price")),
        "priceWithoutVat": bool((c.get("price") or {}).get("extra", {}).get("without_vat")),
        "km": num(specs.get("mileage")),
        "fuel": specs.get("fuel_type"),
        "gearbox": specs.get("gearbox_type"),
        "power_hp": num(specs.get("engine_power")),
        "engine_cc": num(specs.get("engine_size")),
        "doors": num(specs.get("doors")),
        "seats": num(specs.get("seats")),
        "color": specs.get("exterior_color"),
        "interiorColor": specs.get("interior_color"),
        "interiorType": specs.get("interior_type"),
        "bodyType": (c.get("key_features") and next(
            (k.get("value") for k in c["key_features"] if k.get("key") == "category"), None)),
        "driveType": specs.get("drive_type"),
        "emissions": specs.get("euroclass"),
        "co2": specs.get("emissions_co2"),
        "kteo": specs.get("kteo"),
        "circulationTax": specs.get("circulation_tax"),
        "previousOwners": num(specs.get("previous_owners")),
        "airbags": num(specs.get("airbags")),
        "rimSize": specs.get("rim_size"),
        "condition": specs.get("condition"),
        "crashed": bool(c.get("crashed")),
        "description": description_text(c.get("description")),
        "features": [e.get("value") for e in (c.get("extras") or []) if e.get("value")],
        "status": "available",
        "carGrUrl": f"{BASE}/cars/view/{cid}",
        "images": images,
        "imagesThumb": images_thumb,
        "imagesLarge": images_large,
    }
    car["_photoUrls"] = [p["url"] for p in photos]
    return car


def migrate_folders(cars):
    """Aendert sich der Fahrzeugname, aendert sich auch der Ordnername.
    Der Ordner wird dann anhand der car.gr-ID (steht am Ende) umbenannt,
    damit die bereits geladenen Fotos nicht verloren gehen."""
    base = os.path.join(ROOT, "images", "cars")
    if not os.path.isdir(base):
        return
    by_id = {}
    for name in os.listdir(base):
        match = re.search(r"-(\d+)$", name)
        if match:
            by_id[match.group(1)] = name

    for car in cars:
        target = car["id"]
        if os.path.isdir(os.path.join(base, target)):
            continue
        old = by_id.get(str(car["carGrId"]))
        if old and old != target:
            os.rename(os.path.join(base, old), os.path.join(base, target))
            print(f"  Ordner umbenannt: {old} -> {target}")


def download_images(car):
    folder = os.path.join(ROOT, "images", "cars", car["id"])
    os.makedirs(folder, exist_ok=True)
    for i, pattern in enumerate(car["_photoUrls"]):
        targets = [(PHOTO_SIZE, f"{i:03d}.jpg"), (THUMB_SIZE, f"{i:03d}_thumb.jpg")]
        if i < LARGE_COUNT:
            targets.append((LARGE_SIZE, f"{i:03d}_large.jpg"))
        for size, name in targets:
            path = os.path.join(folder, name)
            webp = path[:-4] + ".webp"
            if os.path.exists(webp) and os.path.getsize(webp) > 500:
                continue
            if os.path.exists(path) and os.path.getsize(path) > 1000:
                continue
            url = pattern.replace("{size}", size)
            try:
                data = get(url, binary=True)
            except Exception as error:
                print(f"  ! {url}: {error}")
                continue
            with open(path, "wb") as fh:
                fh.write(data)
            time.sleep(0.05)


def main():
    with_images = "--no-images" not in sys.argv
    ids = find_ids()
    print(f"{len(ids)} Inserate gefunden.")

    # Bestehende Daten als Rueckfallebene: ein 502 oder eine Zeitueberschreitung
    # darf kein Fahrzeug von der Website werfen. Nur 404/410 (auf car.gr wirklich
    # geloescht) fuehren dazu, dass ein Inserat verschwindet.
    previous = {}
    old_path = os.path.join(ROOT, "data", "cars.json")
    if os.path.exists(old_path):
        with open(old_path, encoding="utf-8") as fh:
            previous = {str(c["carGrId"]): c for c in json.load(fh)}

    cars = []
    kept_old = []
    for cid, vehicle_type in ids:
        try:
            classified = fetch_classified(cid, vehicle_type)
        except urllib.error.HTTPError as error:
            if error.code in (404, 410):
                print(f"  - {cid}: auf car.gr geloescht ({error.code}) — faellt raus")
                continue
            if cid in previous:
                print(f"  ! {cid}: {error} — behalte den bisherigen Stand")
                cars.append(dict(previous[cid], _photoUrls=[]))
                kept_old.append(cid)
                continue
            print(f"  ! {cid} uebersprungen: {error}")
            continue
        except Exception as error:
            if cid in previous:
                print(f"  ! {cid}: {error} — behalte den bisherigen Stand")
                cars.append(dict(previous[cid], _photoUrls=[]))
                kept_old.append(cid)
                continue
            print(f"  ! {cid} uebersprungen: {error}")
            continue
        car = build_car(cid, {"data": {"classified": classified}})
        car["vehicleType"] = vehicle_type
        print(f"  {car['brand']} {car['model']} ({car['year']}) — {len(car['images'])} Fotos")
        if with_images:
            download_images(car)
        car.pop("_photoUrls")
        cars.append(car)
        if cached_page(cid) is None:
            time.sleep(PAGE_DELAY)   # car.gr sperrt sonst die Detailseiten (429)

    cars = drop_duplicates(cars)
    migrate_folders(cars)
    cars.sort(key=lambda c: (c["brand"] or "", c["model"] or ""))
    with open(os.path.join(ROOT, "data", "cars.json"), "w", encoding="utf-8") as fh:
        json.dump(cars, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"\ndata/cars.json geschrieben: {len(cars)} Fahrzeuge.")
    if kept_old:
        print(f"  Achtung: {len(kept_old)} davon aus dem bisherigen Stand "
              f"uebernommen, weil car.gr sie gerade nicht auslieferte: "
              f"{', '.join(kept_old)}")
    write_sitemap(cars)

    from build_pages import build as build_pages
    build_pages(cars)


def drop_duplicates(cars):
    """Manche Fahrzeuge stehen auf car.gr doppelt (einmal unter Autos, einmal
    unter Nutzfahrzeuge). Gleiche Marke + Baujahr + km + Preis = dasselbe Auto;
    behalten wird das Inserat mit den meisten Fotos."""
    best = {}
    for car in cars:
        key = (car["brand"], car["year"], car["km"], car["price"])
        current = best.get(key)
        if current is None or len(car["images"]) > len(current["images"]):
            best[key] = car
    kept = [c for c in cars if best.get((c["brand"], c["year"], c["km"], c["price"])) is c]
    removed = len(cars) - len(kept)
    if removed:
        print(f"  {removed} doppelte Anzeige(n) entfernt.")
    return kept


def write_sitemap(cars):
    """sitemap.xml mit Startseite + allen Fahrzeugseiten.
    SITE_URL anpassen, sobald die Domain steht."""
    site = os.environ.get("SITE_URL", "https://www.example.gr").rstrip("/")
    urls = [f"{site}/"] + [f"{site}/cars/{c['id']}.html" for c in cars]
    body = "\n".join(
        f"  <url><loc>{u.replace('&', '&amp;')}</loc>"
        f"<priority>{'1.0' if i == 0 else '0.8'}</priority></url>"
        for i, u in enumerate(urls))
    xml = ('<?xml version="1.0" encoding="UTF-8"?>\n'
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
           f"{body}\n</urlset>\n")
    with open(os.path.join(ROOT, "sitemap.xml"), "w", encoding="utf-8") as fh:
        fh.write(xml)
    print(f"sitemap.xml geschrieben ({len(urls)} URLs, Basis {site}).")


if __name__ == "__main__":
    main()
