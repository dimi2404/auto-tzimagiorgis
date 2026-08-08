/* Fahrzeug-Detailseite.

   Alle Texte, Preise und Tabellen stehen bereits fertig im HTML (erzeugt von
   tools/build_pages.py) — das ist wichtig für Google und für die Vorschau beim
   Teilen. Dieses Skript hängt nur noch die Fotogalerie und die Lightbox an. */

import { createGallery, createLightbox } from './gallery.js';
import { loadSite, initHeader, initYear } from './site.js';

function init() {
  initHeader();
  initYear();
  loadSite('../data/site.json').catch((error) => console.error(error));

  const dataNode = document.querySelector('#car-data');
  const stage = document.querySelector('#stage');
  if (!dataNode || !stage) return;

  const car = JSON.parse(dataNode.textContent);
  // Die Seiten liegen in /cars/, die Bilder eine Ebene höher.
  car.images = (car.images || []).map((src) => `../${src}`);
  car.imagesThumb = (car.imagesThumb || []).map((src) => `../${src}`);
  car.imagesLarge = (car.imagesLarge || []).map((src) => `../${src}`);
  if (!car.images.length) return;

  const gallery = createGallery(car);
  stage.innerHTML = '';
  stage.appendChild(gallery.el);

  const openLightbox = createLightbox(gallery);
  gallery.el.querySelector('.gallery__zoom').addEventListener('click', openLightbox);
  gallery.el.querySelector('.gallery__image').addEventListener('click', openLightbox);
}

init();
