#!/usr/bin/env python3
"""Erzeugt Platzhalter-Bilder (SVG) fuer jedes Auto aus data/cars.json.

Pro Auto werden FRAMES Bilder erzeugt, die eine Drehung um die eigene Achse
andeuten (Seitenansicht -> Front -> andere Seite). Sobald echte Fotos vorliegen,
einfach images/cars/<id>/ mit den echten Dateien fuellen und die Dateinamen in
cars.json eintragen -- dieses Skript wird dann nicht mehr gebraucht.
"""
import json
import math
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRAMES = 12


def shade(hex_color, factor):
    hex_color = hex_color.lstrip("#")
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
    r, g, b = (max(0, min(255, int(c * factor))) for c in (r, g, b))
    return f"#{r:02x}{g:02x}{b:02x}"


def frame_svg(car, index):
    angle = 360.0 * index / FRAMES
    rad = math.radians(angle)
    # Seitenansicht wird horizontal gestaucht -> wirkt wie eine Drehung.
    squeeze = math.cos(rad)
    scale_x = max(abs(squeeze), 0.28) * (1 if squeeze >= 0 else -1)
    # Front/Heck (squeeze nahe 0) etwas dunkler, damit die Drehung lesbar ist.
    depth = 0.82 + 0.18 * abs(squeeze)
    body = shade(car.get("colorHex", "#6b7078"), depth)
    body_dark = shade(car.get("colorHex", "#6b7078"), depth * 0.7)
    glass = shade("#7f8b99", depth)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 320" width="640" height="320" role="img" aria-label="{car['brand']} {car['model']}">
  <defs>
    <linearGradient id="b" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0" stop-color="{body}"/>
      <stop offset="1" stop-color="{body_dark}"/>
    </linearGradient>
    <radialGradient id="sh" cx="0.5" cy="0.5" r="0.5">
      <stop offset="0" stop-color="#000" stop-opacity=".45"/>
      <stop offset="1" stop-color="#000" stop-opacity="0"/>
    </radialGradient>
  </defs>
  <ellipse cx="320" cy="268" rx="{abs(scale_x) * 210 + 60:.0f}" ry="26" fill="url(#sh)"/>
  <g transform="translate(320 190) scale({scale_x:.4f} 1) translate(-320 -190)">
    <path d="M110 210 L128 152 Q140 126 176 120 L300 108 Q352 104 396 128 L470 168 Q520 176 528 196 L530 214 Q530 226 516 226 L124 226 Q110 226 110 214 Z" fill="url(#b)"/>
    <path d="M170 148 Q182 130 212 126 L292 118 Q330 116 362 136 L406 164 L182 168 Z" fill="{glass}" opacity=".85"/>
    <path d="M286 120 L292 166" stroke="{body_dark}" stroke-width="5" fill="none"/>
    <rect x="118" y="196" width="404" height="6" fill="{body_dark}" opacity=".5"/>
  </g>
  <g fill="#111318">
    <circle cx="{320 - abs(scale_x) * 130:.0f}" cy="224" r="{22 * (0.6 + 0.4 * abs(scale_x)):.0f}"/>
    <circle cx="{320 + abs(scale_x) * 150:.0f}" cy="224" r="{22 * (0.6 + 0.4 * abs(scale_x)):.0f}"/>
  </g>
</svg>
"""


def main():
    with open(os.path.join(ROOT, "data", "cars.json"), encoding="utf-8") as fh:
        cars = json.load(fh)

    for car in cars:
        out_dir = os.path.join(ROOT, "images", "cars", car["id"])
        os.makedirs(out_dir, exist_ok=True)
        images = []
        for i in range(FRAMES):
            name = f"{i + 1:02d}.svg"
            with open(os.path.join(out_dir, name), "w", encoding="utf-8") as fh:
                fh.write(frame_svg(car, i))
            images.append(f"images/cars/{car['id']}/{name}")
        car["images"] = images

    with open(os.path.join(ROOT, "data", "cars.json"), "w", encoding="utf-8") as fh:
        json.dump(cars, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    print(f"{len(cars)} Autos x {FRAMES} Platzhalter-Frames erzeugt.")


if __name__ == "__main__":
    main()
