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
import urllib.request

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

    cars = []
    for cid, vehicle_type in ids:
        payload = json.loads(get(f"{BASE}/api/classifieds/{cid}/"))
        car = build_car(cid, payload)
        car["vehicleType"] = vehicle_type
        print(f"  {car['brand']} {car['model']} ({car['year']}) — {len(car['images'])} Fotos")
        if with_images:
            download_images(car)
        car.pop("_photoUrls")
        cars.append(car)

    cars = drop_duplicates(cars)
    migrate_folders(cars)
    cars.sort(key=lambda c: (c["brand"] or "", c["model"] or ""))
    with open(os.path.join(ROOT, "data", "cars.json"), "w", encoding="utf-8") as fh:
        json.dump(cars, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"\ndata/cars.json geschrieben: {len(cars)} Fahrzeuge.")
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
