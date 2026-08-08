#!/usr/bin/env python3
"""Erzeugt fuer jedes Fahrzeug eine eigene HTML-Seite unter cars/<id>.html.

Warum: mit einer einzigen car.html?id=… kennt Google nur eine Seite und beim
Teilen per WhatsApp/Facebook erscheint kein Vorschaubild. Jede Seite bringt
eigene Meta-Tags, ein og:image und strukturierte Daten (schema.org/Car) mit —
und der komplette Inhalt steht direkt im HTML, nicht erst nach dem JavaScript.

Wird von import-cargr.py am Ende automatisch aufgerufen.
"""
import html
import json
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT_DIR = os.path.join(ROOT, "cars")
SITE_URL = os.environ.get("SITE_URL", "").rstrip("/")


def esc(value):
    return html.escape(str(value), quote=True)


def fmt_int(value):
    return f"{value:,}".replace(",", ".") if isinstance(value, int) else value


def fmt_price(value):
    return f"{fmt_int(value)} €" if value else "Κατόπιν συνεννόησης"


def key_facts(car):
    rows = [
        ("Χρονολογία", car.get("registration") or car.get("year")),
        ("Χιλιόμετρα", f"{fmt_int(car['km'])} χλμ." if car.get("km") is not None else None),
        ("Καύσιμο", car.get("fuel")),
        ("Κιβώτιο", car.get("gearbox")),
        ("Ιπποδύναμη", f"{car['power_hp']} hp" if car.get("power_hp") else None),
        ("Κυβικά", f"{fmt_int(car['engine_cc'])} cc" if car.get("engine_cc") else None),
    ]
    return [(label, value) for label, value in rows if value not in (None, "")]


def spec_rows(car):
    rows = [
        ("Μάρκα", car.get("brand")),
        ("Μοντέλο", car.get("modelFull") or car.get("model")),
        ("Χρονολογία", car.get("registration") or car.get("year")),
        ("Χιλιόμετρα", f"{fmt_int(car['km'])} χλμ." if car.get("km") is not None else None),
        ("Καύσιμο", car.get("fuel")),
        ("Κιβώτιο", car.get("gearbox")),
        ("Ισχύς", f"{car['power_hp']} hp" if car.get("power_hp") else None),
        ("Κυβικά", f"{fmt_int(car['engine_cc'])} cc" if car.get("engine_cc") else None),
        ("Κατηγορία", car.get("bodyType")),
        ("Κίνηση τροχών", car.get("driveType")),
        ("Πόρτες", car.get("doors")),
        ("Θέσεις", car.get("seats")),
        ("Χρώμα", car.get("color")),
        ("Χρώμα εσωτερικού", car.get("interiorColor")),
        ("Επένδυση σαλονιού", car.get("interiorType")),
        ("Κλάση ρύπων", car.get("emissions")),
        ("Εκπομπές CO₂", car.get("co2")),
        ("Μέγεθος ζάντας", car.get("rimSize")),
        ("Αερόσακοι", car.get("airbags")),
        ("Σύνολο κατόχων", car.get("previousOwners")),
        ("ΚΤΕΟ", car.get("kteo")),
        ("Τέλη κυκλοφορίας", car.get("circulationTax")),
        ("Κατάσταση", car.get("condition")),
    ]
    return [(label, value) for label, value in rows if value not in (None, "")]


def json_ld(car, site, url, image_url):
    data = {
        "@context": "https://schema.org",
        "@type": "Car",
        "name": f"{car['brand']} {car.get('modelFull') or car['model']} {car.get('year', '')}".strip(),
        "brand": {"@type": "Brand", "name": car["brand"]},
        "model": car.get("modelFull") or car.get("model"),
        "vehicleModelDate": car.get("year"),
        "mileageFromOdometer": {"@type": "QuantitativeValue",
                                "value": car.get("km"), "unitCode": "KMT"},
        "fuelType": car.get("fuel"),
        "vehicleTransmission": car.get("gearbox"),
        "numberOfDoors": car.get("doors"),
        "seatingCapacity": car.get("seats"),
        "color": car.get("color"),
        "offers": {
            "@type": "Offer",
            "price": car.get("price"),
            "priceCurrency": "EUR",
            "availability": "https://schema.org/InStock"
                            if car.get("status") == "available"
                            else "https://schema.org/SoldOut",
            "seller": {"@type": "AutoDealer", "name": site.get("name"),
                       "telephone": site.get("phone")},
        },
    }
    if image_url:
        data["image"] = image_url
    if url:
        data["url"] = url
    data = {k: v for k, v in data.items() if v not in (None, "")}
    return json.dumps(data, ensure_ascii=False, indent=2)


def render(car, site):
    name = car.get("modelFull") or car.get("model")
    title = f"{car['brand']} {name} {car.get('year', '')} — {site.get('nameShort', '')}".strip()
    cover = car["images"][0] if car.get("images") else ""
    cover_large = (car.get("imagesLarge") or [cover])[0]

    bits = [car['brand'], name, str(car.get('year') or '')]
    if car.get("km") is not None:
        bits.append(f"{fmt_int(car['km'])} χλμ.")
    if car.get("fuel"):
        bits.append(car["fuel"])
    bits.append(fmt_price(car.get("price")))
    description = " · ".join(b for b in bits if b) + \
        ". Εισαγωγή από τη Γερμανία, με έλεγχο και εγγύηση."

    page_url = f"{SITE_URL}/cars/{car['id']}.html" if SITE_URL else ""
    image_url = f"{SITE_URL}/{cover_large}" if SITE_URL else ""

    flags = []
    if car.get("vehicleType"):
        flags.append(f'<span class="flag">{esc(car["vehicleType"])}</span>')
    if car.get("priceWithoutVat"):
        flags.append('<span class="flag">Χωρίς ΦΠΑ</span>')
    if car.get("crashed"):
        flags.append('<span class="flag flag--warn">Με ζημιά</span>')
    if car.get("status") == "reserved":
        flags.append('<span class="flag flag--warn">Κρατημένο</span>')

    subject = f"Ενδιαφέρομαι για: {car['brand']} {name} ({car.get('year', '')})"
    wa_number = "".join(ch for ch in (site.get("mobile") or site.get("phone", "")) if ch.isdigit())
    mail_body = (f"Καλησπέρα,\n\nενδιαφέρομαι για το {car['brand']} {name} "
                 f"του {car.get('year', '')} ({fmt_price(car.get('price'))}).\n"
                 f"Παρακαλώ επικοινωνήστε μαζί μου.\n\nΌνομα:\nΤηλέφωνο:")

    from urllib.parse import quote
    facts = "\n".join(
        f'          <li><span>{esc(k)}</span><b>{esc(v)}</b></li>' for k, v in key_facts(car))
    specs = "\n".join(
        f'            <tr><th>{esc(k)}</th><td>{esc(v)}</td></tr>' for k, v in spec_rows(car))
    features = "".join(f'<li>{esc(f)}</li>' for f in car.get("features") or [])

    # Nur die Bilddaten wandern ins JavaScript — den Rest liefert das HTML.
    gallery_data = json.dumps({
        "brand": car["brand"],
        "modelFull": name,
        "images": car.get("images") or [],
        "imagesThumb": car.get("imagesThumb") or [],
        "imagesLarge": car.get("imagesLarge") or [],
    }, ensure_ascii=False)

    return f"""<!DOCTYPE html>
<html lang="el">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)}</title>
<meta name="description" content="{esc(description)}">
<meta name="theme-color" content="#ae252b">
{f'<link rel="canonical" href="{esc(page_url)}">' if page_url else ''}
<meta property="og:type" content="website">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{esc(description)}">
<meta property="og:locale" content="el_GR">
{f'<meta property="og:url" content="{esc(page_url)}">' if page_url else ''}
{f'<meta property="og:image" content="{esc(image_url)}">' if image_url else ''}
<meta name="twitter:card" content="summary_large_image">
<link rel="icon" href="../images/favicon.svg" type="image/svg+xml">
<link rel="stylesheet" href="../assets/css/main.css">
<script type="application/ld+json">
{json_ld(car, site, page_url, image_url)}
</script>
</head>
<body>

<header class="header is-stuck">
  <div class="container header__inner">
    <a class="logo" href="../index.html"><img class="logo__mark" src="../images/logo-jk-hell.png" alt="JK" width="382" height="520">
      <span class="logo__name"><b>ΕΜΠΟΡΙΑ ΑΥΤΟΚΙΝΗΤΩΝ</b><i>Τζημαγιώργης</i></span></a>
    <nav class="nav" id="nav">
      <a href="../index.html#cars">Αυτοκίνητα</a>
      <a href="../index.html#about">Σχετικά με εμάς</a>
      <a href="../index.html#contact">Επικοινωνία</a>
    </nav>
    <a class="header__phone" data-site="phoneDisplay" data-site-href="tel:phone"
       href="tel:{esc(site.get('phone', ''))}">{esc(site.get('phoneDisplay', ''))}</a>
    <button class="nav-toggle" type="button" aria-controls="nav" aria-expanded="false" aria-label="Μενού">☰</button>
  </div>
</header>

<main class="detail container">
  <p class="breadcrumb"><a href="../index.html">Αρχική</a> › <a href="../index.html#cars">Αυτοκίνητα</a>
     › <span>{esc(car['brand'])} {esc(name)}</span></p>

  <div class="detail__grid">
    <div class="detail__stage" id="stage">
      <noscript><img src="../{esc(cover)}" alt="{esc(car['brand'])} {esc(name)}"></noscript>
    </div>
    <div>
      <span class="eyebrow">{esc(car['brand'])}</span>
      <h1 class="detail__title">{esc(name)}</h1>
      <p class="detail__price">{esc(fmt_price(car.get('price')))}</p>
      {f'<div class="flags" style="margin:-14px 0 24px">{"".join(flags)}</div>' if flags else ''}

      <div class="detail__actions">
        <a class="btn btn--primary" href="tel:{esc(site.get('phone', ''))}">Κλήση</a>
        <a class="btn btn--whatsapp" href="https://wa.me/{wa_number}?text={quote(subject)}"
           target="_blank" rel="noopener">WhatsApp</a>
        <a class="btn btn--ghost" href="mailto:{esc(site.get('email', ''))}?subject={quote(subject)}&amp;body={quote(mail_body)}">Email</a>
      </div>

      <ul class="key-facts">
{facts}
      </ul>

      <h2 class="detail__subtitle">Αναλυτικά χαρακτηριστικά</h2>
      <table class="spec-table">
        <tbody>
{specs}
        </tbody>
      </table>

      {f'<h2 class="detail__subtitle">Εξοπλισμός</h2><ul class="tags">{features}</ul>' if features else ''}
      {f'<h2 class="detail__subtitle">Περιγραφή</h2><p style="color:var(--grey-300)">{esc(car["description"])}</p>' if car.get('description') else ''}

      <p><a href="{esc(car.get('carGrUrl', ''))}" target="_blank" rel="noopener"
            style="color:var(--grey-500)">Δείτε την αγγελία στο car.gr ↗</a></p>
      <p style="margin-top:20px"><a href="../index.html#cars" style="color:var(--grey-500)">‹ Πίσω σε όλα τα οχήματα</a></p>
    </div>
  </div>
</main>

<footer class="footer">
  <div class="container footer__inner">
    <span>© <span data-year>2026</span> ΤΖΗΜΑΓΙΩΡΓΗΣ — Εισαγωγή αυτοκινήτων από τη Γερμανία</span>
    <span><a href="../legal.html">Στοιχεία επιχείρησης</a> · <a href="../privacy.html">Απόρρητο</a></span>
  </div>
</footer>

<div class="lightbox" id="lightbox" role="dialog" aria-modal="true" aria-label="Φωτογραφία οχήματος">
  <button class="lightbox__close" type="button" aria-label="Κλείσιμο">✕</button>
  <button class="lightbox__nav lightbox__prev" type="button" aria-label="Προηγούμενη φωτογραφία">‹</button>
  <img src="" alt="">
  <button class="lightbox__nav lightbox__next" type="button" aria-label="Επόμενη φωτογραφία">›</button>
  <span class="lightbox__counter"></span>
</div>

<script id="car-data" type="application/json">{gallery_data}</script>
<script type="module" src="../assets/js/detail.js"></script>
</body>
</html>
"""


def build(cars=None, site=None):
    if cars is None:
        with open(os.path.join(ROOT, "data", "cars.json"), encoding="utf-8") as fh:
            cars = json.load(fh)
    if site is None:
        with open(os.path.join(ROOT, "data", "site.json"), encoding="utf-8") as fh:
            site = json.load(fh)

    os.makedirs(OUT_DIR, exist_ok=True)
    wanted = set()
    for car in cars:
        name = f"{car['id']}.html"
        wanted.add(name)
        with open(os.path.join(OUT_DIR, name), "w", encoding="utf-8") as fh:
            fh.write(render(car, site))

    # Seiten verkaufter Fahrzeuge entfernen
    for old in os.listdir(OUT_DIR):
        if old.endswith(".html") and old not in wanted:
            os.remove(os.path.join(OUT_DIR, old))
            print(f"  Seite entfernt: cars/{old}")

    print(f"{len(cars)} Fahrzeugseiten unter cars/ erzeugt.")


if __name__ == "__main__":
    build()
