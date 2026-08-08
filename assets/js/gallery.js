/* Fotogalerie für die Fahrzeug-Detailseite.

   Grosses Bild + Pfeile + Zähler + Thumbnail-Leiste, dazu eine Lightbox.
   (Die frühere 360°-Drehplattform wurde entfernt — sie kommt später zurück.) */

/** Grosses Bild einer Galerie: zeigt das Foto immer vollständig (contain). */
export function createGallery(car) {
  const images = car.images || [];
  const large = car.imagesLarge || [];
  const src = (i) => large[i] || images[i];

  const root = document.createElement('div');
  root.className = 'gallery';
  root.innerHTML = `
    <div class="gallery__stage">
      <img class="gallery__image" alt="" width="1024" height="576" decoding="async">
      <button class="gallery__nav gallery__nav--prev" type="button" aria-label="Προηγούμενη φωτογραφία">‹</button>
      <button class="gallery__nav gallery__nav--next" type="button" aria-label="Επόμενη φωτογραφία">›</button>
      <span class="gallery__counter"></span>
      <button class="gallery__zoom" type="button" aria-label="Μεγέθυνση φωτογραφίας">⤢</button>
    </div>
    <div class="thumbs"></div>
  `;

  const image = root.querySelector('.gallery__image');
  const counter = root.querySelector('.gallery__counter');
  const thumbs = root.querySelector('.thumbs');
  let index = 0;

  // Thumbnails erst laden, wenn sie in der Leiste sichtbar werden. `loading="lazy"`
  // allein reicht hier nicht: bei waagerechtem Scrollen laedt der Browser sonst
  // die halbe Serie sofort.
  const thumbSources = (car.imagesThumb && car.imagesThumb.length === images.length)
    ? car.imagesThumb
    : images;

  images.forEach((_, i) => {
    const button = document.createElement('button');
    button.type = 'button';
    button.setAttribute('aria-label', `Φωτογραφία ${i + 1}`);
    button.innerHTML = `<img alt="" width="160" height="120" decoding="async"
                             data-src="${thumbSources[i]}">`;
    button.addEventListener('click', () => show(i));
    thumbs.appendChild(button);
  });

  const lazyThumbs = thumbs.querySelectorAll('img[data-src]');
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => {
        if (!entry.isIntersecting) return;
        const img = entry.target;
        img.src = img.dataset.src;
        delete img.dataset.src;
        observer.unobserve(img);
      });
    }, { root: thumbs, rootMargin: '200px' });
    lazyThumbs.forEach((img) => observer.observe(img));
  } else {
    lazyThumbs.forEach((img) => { img.src = img.dataset.src; });
  }

  function show(next) {
    if (!images.length) return;
    index = ((next % images.length) + images.length) % images.length;
    image.src = src(index);
    image.alt = `${car.brand} ${car.modelFull || car.model} — φωτογραφία ${index + 1}`;
    counter.textContent = `${index + 1} / ${images.length}`;
    [...thumbs.children].forEach((b, i) => b.classList.toggle('is-active', i === index));
    const active = thumbs.children[index];
    if (active) active.scrollIntoView({ block: 'nearest', inline: 'nearest' });
    root.dispatchEvent(new CustomEvent('change', { detail: { index } }));
  }

  root.querySelector('.gallery__nav--prev').addEventListener('click', () => show(index - 1));
  root.querySelector('.gallery__nav--next').addEventListener('click', () => show(index + 1));

  // Wischen auf dem Handy
  let startX = null;
  root.querySelector('.gallery__stage').addEventListener('touchstart', (e) => {
    startX = e.touches[0].clientX;
  }, { passive: true });
  root.querySelector('.gallery__stage').addEventListener('touchend', (e) => {
    if (startX === null) return;
    const delta = e.changedTouches[0].clientX - startX;
    if (Math.abs(delta) > 40) show(index + (delta < 0 ? 1 : -1));
    startX = null;
  });

  document.addEventListener('keydown', (e) => {
    // Bei offener Lightbox übernimmt deren eigener Handler die Pfeiltasten.
    const lightbox = document.querySelector('#lightbox');
    if (lightbox && lightbox.hasAttribute('open')) return;
    if (e.key === 'ArrowLeft') show(index - 1);
    if (e.key === 'ArrowRight') show(index + 1);
  });

  show(0);
  return { el: root, show, get index() { return index; }, images, src };
}

/** Vollbild-Ansicht. */
export function createLightbox(gallery) {
  const box = document.querySelector('#lightbox');
  if (!box) return () => {};
  const img = box.querySelector('img');
  const counter = box.querySelector('.lightbox__counter');

  const paint = () => {
    img.src = gallery.src(gallery.index);
    img.alt = 'Φωτογραφία οχήματος';
    if (counter) counter.textContent = `${gallery.index + 1} / ${gallery.images.length}`;
  };
  const open = () => { paint(); box.setAttribute('open', ''); document.body.style.overflow = 'hidden'; };
  const close = () => { box.removeAttribute('open'); document.body.style.overflow = ''; };
  const step = (delta) => { gallery.show(gallery.index + delta); paint(); };

  box.querySelector('.lightbox__close').addEventListener('click', close);
  box.querySelector('.lightbox__prev').addEventListener('click', (e) => { e.stopPropagation(); step(-1); });
  box.querySelector('.lightbox__next').addEventListener('click', (e) => { e.stopPropagation(); step(1); });
  box.addEventListener('click', (e) => { if (e.target === box || e.target === img) close(); });
  document.addEventListener('keydown', (e) => {
    if (!box.hasAttribute('open')) return;
    if (e.key === 'Escape') close();
    if (e.key === 'ArrowLeft') step(-1);
    if (e.key === 'ArrowRight') step(1);
  });

  return open;
}
