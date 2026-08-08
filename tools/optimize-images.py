#!/usr/bin/env python3
"""Wandelt alle Fahrzeugfotos von JPG nach WebP um (ca. halbe Dateigroesse
bei gleicher Qualitaet) und loescht die JPGs.

Aufruf:
    python3 tools/optimize-images.py           # umwandeln
    python3 tools/optimize-images.py --keep    # JPGs behalten

Danach einmal `python3 tools/import-cargr.py --no-images` laufen lassen,
damit die Pfade in data/cars.json und die Fahrzeugseiten aktualisiert werden.
"""
import os
import sys

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CARS_DIR = os.path.join(ROOT, "images", "cars")
QUALITY = 80


def convert(path, keep_jpg=False):
    target = path[:-4] + ".webp"
    if os.path.exists(target):
        if not keep_jpg:
            os.remove(path)
        return 0, 0
    try:
        with Image.open(path) as img:
            img.save(target, "WEBP", quality=QUALITY, method=4)
    except Exception as error:
        print(f"  ! {path}: {error}")
        return 0, 0
    before, after = os.path.getsize(path), os.path.getsize(target)
    if not keep_jpg:
        os.remove(path)
    return before, after


def main():
    keep_jpg = "--keep" in sys.argv
    total_before = total_after = count = 0

    for folder, _, files in os.walk(CARS_DIR):
        for name in sorted(files):
            if not name.lower().endswith(".jpg"):
                continue
            before, after = convert(os.path.join(folder, name), keep_jpg)
            total_before += before
            total_after += after
            count += 1
            if count % 250 == 0:
                print(f"  {count} Bilder …")

    if total_before:
        saved = 100 - total_after / total_before * 100
        print(f"\n{count} Bilder umgewandelt: "
              f"{total_before/1024/1024:.0f} MB -> {total_after/1024/1024:.0f} MB "
              f"({saved:.0f} % kleiner)")
    else:
        print(f"{count} Bilder geprüft, nichts umzuwandeln.")


if __name__ == "__main__":
    main()
