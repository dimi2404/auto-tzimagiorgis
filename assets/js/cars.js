/* Startseite: Auto-Grid, Filter, Sortierung, Kontaktformular. */

import { fmtPrice, fmtNumber, loadJSON, loadSite, initHeader, initReveal, initYear } from './site.js';

const grid = document.querySelector('#cars-grid');
const count = document.querySelector('#results-count');
const filters = {
  type: document.querySelector('#filter-type'),
  brand: document.querySelector('#filter-brand'),
  fuel: document.querySelector('#filter-fuel'),
  gearbox: document.querySelector('#filter-gearbox'),
  price: document.querySelector('#filter-price'),
  sort: document.querySelector('#filter-sort'),
};

let allCars = [];

function fillOptions(select, values) {
  values.sort((a, b) => String(a).localeCompare(String(b), 'el'));
  values.forEach((value) => {
    const option = document.createElement('option');
    option.value = value;
    option.textContent = value;
    select.appendChild(option);
  });
}

function buildCard(car) {
  const card = document.createElement('article');
  card.className = 'car-card reveal';

  // Titelbild wie bei car.gr: ein Foto, sauber formatfüllend.
  const cover = car.images && car.images[0];
  const photos = (car.images || []).length;
  const media = document.createElement('a');
  media.className = 'car-card__media';
  media.href = `cars/${car.id}.html`;
  media.innerHTML = `
    ${cover ? `<img src="${cover}" alt="${car.brand} ${car.modelFull || car.model}" loading="lazy" decoding="async" width="575" height="431">`
            : '<span class="car-card__nophoto">Χωρίς φωτογραφία</span>'}
    ${photos ? `<span class="car-card__count">${photos} φωτογραφίες</span>` : ''}
    ${car.status === 'reserved' ? '<span class="car-card__badge">Κρατημένο</span>' : ''}
  `;
  card.appendChild(media);

  const flags = [];
  if (car.priceWithoutVat) flags.push('<span class="flag">Χωρίς ΦΠΑ</span>');
  if (car.crashed) flags.push('<span class="flag flag--warn">Με ζημιά</span>');

  const body = document.createElement('div');
  body.className = 'car-card__body';
  body.innerHTML = `
    <span class="car-card__brand">${car.brand}</span>
    <h3 class="car-card__title"><a href="cars/${car.id}.html">${car.modelFull || car.model}</a></h3>
    <ul class="car-card__specs">
      <li><span>Χρονολογία</span><b>${car.year || '—'}</b></li>
      <li><span>Χιλιόμετρα</span><b>${car.km != null ? fmtNumber(car.km) + ' χλμ.' : '—'}</b></li>
      <li><span>Καύσιμο</span><b>${car.fuel || '—'}</b></li>
      ${car.gearbox
        ? `<li><span>Κιβώτιο</span><b>${car.gearbox}</b></li>`
        // Bei Nutzfahrzeugen fehlt auf car.gr oft das Getriebe — dann lieber
        // die Leistung zeigen als einen leeren Strich.
        : `<li><span>Ιπποδύναμη</span><b>${car.power_hp ? car.power_hp + ' hp' : '—'}</b></li>`}
    </ul>
    ${flags.length ? `<div class="flags">${flags.join('')}</div>` : ''}
    <div class="car-card__foot">
      <span class="price"><small>Τιμή</small>${car.price ? fmtPrice(car.price) : 'Κατόπιν συνεννόησης'}</span>
      <a class="btn btn--primary" href="cars/${car.id}.html">Λεπτομέρειες</a>
    </div>
  `;
  card.appendChild(body);
  return card;
}

function apply() {
  const type = filters.type.value;
  const brand = filters.brand.value;
  const fuel = filters.fuel.value;
  const gearbox = filters.gearbox.value;
  const maxPrice = Number(filters.price.value) || Infinity;

  let list = allCars.filter((car) =>
    (!type || car.vehicleType === type) &&
    (!brand || car.brand === brand) &&
    (!fuel || car.fuel === fuel) &&
    (!gearbox || car.gearbox === gearbox) &&
    (car.price || 0) <= maxPrice
  );

  const sorters = {
    'price-asc': (a, b) => (a.price || 0) - (b.price || 0),
    'price-desc': (a, b) => (b.price || 0) - (a.price || 0),
    'year-desc': (a, b) => (b.year || 0) - (a.year || 0),
    'km-asc': (a, b) => (a.km || 0) - (b.km || 0),
  };
  const sorter = sorters[filters.sort.value];
  if (sorter) list = [...list].sort(sorter);

  grid.innerHTML = '';
  if (!list.length) {
    grid.innerHTML = '<p class="empty-state">Δεν βρέθηκαν αυτοκίνητα με αυτά τα κριτήρια. Δοκιμάστε άλλο φίλτρο.</p>';
  } else {
    list.forEach((car) => grid.appendChild(buildCard(car)));
  }
  count.textContent = `${list.length} από ${allCars.length} οχήματα`;
  initReveal(grid);
}

/* WhatsApp-Links aus site.json aufbauen (Nummer ohne + und Leerzeichen). */
function initWhatsApp(site) {
  const number = (site.whatsapp || site.mobile || '').replace(/[^\d]/g, '');
  if (!number) return;
  const text = encodeURIComponent(
    'Καλησπέρα! Ενδιαφέρομαι για ένα από τα οχήματά σας.');
  document.querySelectorAll('#header-wa, #hero-wa').forEach((el) => {
    el.href = `https://wa.me/${number}?text=${text}`;
  });
}

/* Google-Karte erst auf Klick nachladen — vorher werden keine Google-Cookies
   gesetzt, dadurch braucht die Seite kein Cookie-Banner. */
function initMapConsent(site) {
  const box = document.querySelector('#map-consent');
  const button = document.querySelector('#map-load');
  if (!box || !button) return;
  button.addEventListener('click', () => {
    const query = encodeURIComponent(site.mapQuery || `${site.address}, ${site.city}`);
    const frame = document.createElement('iframe');
    frame.className = 'map';
    frame.title = 'Χάρτης';
    frame.loading = 'lazy';
    frame.referrerPolicy = 'no-referrer-when-downgrade';
    frame.src = `https://www.google.com/maps?q=${query}&z=15&output=embed`;
    box.replaceWith(frame);
  });
}

function initContactForm(site) {
  const form = document.querySelector('#contact-form');
  if (!form) return;
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const data = new FormData(form);
    const subject = `Επικοινωνία από την ιστοσελίδα — ${data.get('name')}`;
    const body = [
      `Όνομα: ${data.get('name')}`,
      `Τηλέφωνο: ${data.get('phone')}`,
      `Email: ${data.get('email')}`,
      '',
      data.get('message'),
    ].join('\n');
    window.location.href = `mailto:${site.email}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
  });
}

async function init() {
  initHeader();
  initYear();
  const [site, cars] = await Promise.all([loadSite(), loadJSON('data/cars.json')]);
  allCars = cars;

  fillOptions(filters.type, [...new Set(cars.map((c) => c.vehicleType).filter(Boolean))]);
  fillOptions(filters.brand, [...new Set(cars.map((c) => c.brand).filter(Boolean))]);
  fillOptions(filters.fuel, [...new Set(cars.map((c) => c.fuel).filter(Boolean))]);
  fillOptions(filters.gearbox, [...new Set(cars.map((c) => c.gearbox).filter(Boolean))]);

  Object.values(filters).forEach((select) => select.addEventListener('change', apply));
  document.querySelector('#filter-reset').addEventListener('click', () => {
    Object.values(filters).forEach((select) => (select.value = ''));
    apply();
  });

  const points = document.querySelector('#about-points');
  if (points && site.about && site.about.points) {
    points.innerHTML = site.about.points
      .map((p) => `<li><b>${p.title}</b><span>${p.text}</span></li>`).join('');
  }

  const hours = document.querySelector('#hours');
  if (hours && site.hours) {
    hours.innerHTML = site.hours.map((h) => `<li><span>${h.days}</span><b>${h.time}</b></li>`).join('');
  }

  initWhatsApp(site);
  initMapConsent(site);
  apply();
  initReveal();
  initContactForm(site);

  const stat = document.querySelector('[data-stat="cars"]');
  if (stat) stat.textContent = cars.length;
  const brands = document.querySelector('[data-stat="brands"]');
  if (brands) brands.textContent = new Set(cars.map((c) => c.brand)).size;
  const photos = document.querySelector('[data-stat="photos"]');
  if (photos) photos.textContent = fmtNumber(cars.reduce((sum, c) => sum + (c.images || []).length, 0));
}

init().catch((error) => {
  console.error(error);
  if (grid) grid.innerHTML = '<p class="empty-state">Παρουσιάστηκε σφάλμα κατά τη φόρτωση των αυτοκινήτων.</p>';
});
