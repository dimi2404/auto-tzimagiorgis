/* Gemeinsame Helfer: Daten laden, Formatierung, Header, Reveal-Animation. */

export const fmtPrice = (value) =>
  new Intl.NumberFormat('el-GR', { style: 'currency', currency: 'EUR', maximumFractionDigits: 0 }).format(value);

export const fmtNumber = (value) => new Intl.NumberFormat('el-GR').format(value);

export async function loadJSON(path) {
  const res = await fetch(path, { cache: 'no-cache' });
  if (!res.ok) throw new Error(`${path}: ${res.status}`);
  return res.json();
}

export async function loadSite(path = 'data/site.json') {
  const site = await loadJSON(path);
  const read = (key) => key.split('.').reduce((acc, part) => (acc ? acc[part] : ''), site);

  document.querySelectorAll('[data-site]').forEach((el) => {
    const value = read(el.dataset.site);
    if (value === undefined || value === null || value === '') {
      // Leere Angabe (z. B. kein FAX): die ganze Zeile ausblenden.
      const row = el.closest('li, tr');
      if (row) row.hidden = true;
      return;
    }
    el.textContent = value;
  });

  // data-site-href="tel:phone" -> href="tel:+30…" (Präfix vor dem Doppelpunkt bleibt erhalten)
  document.querySelectorAll('[data-site-href]').forEach((el) => {
    const [scheme, path] = el.dataset.siteHref.split(':');
    const value = read(path);
    if (value) el.setAttribute('href', `${scheme}:${String(value).replace(/\s/g, '')}`);
  });
  return site;
}

export function initHeader() {
  const header = document.querySelector('.header');
  const toggle = document.querySelector('.nav-toggle');
  const nav = document.querySelector('.nav');

  const onScroll = () => header.classList.toggle('is-stuck', window.scrollY > 24);
  onScroll();
  window.addEventListener('scroll', onScroll, { passive: true });

  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      const open = nav.classList.toggle('is-open');
      toggle.setAttribute('aria-expanded', String(open));
    });
    nav.addEventListener('click', (e) => {
      if (e.target.tagName === 'A') {
        nav.classList.remove('is-open');
        toggle.setAttribute('aria-expanded', 'false');
      }
    });
  }
}

export function initReveal(root = document) {
  const items = root.querySelectorAll('.reveal');
  if (!('IntersectionObserver' in window)) {
    items.forEach((el) => el.classList.add('is-visible'));
    return;
  }
  const observer = new IntersectionObserver((entries) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        entry.target.classList.add('is-visible');
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0, rootMargin: '0px 0px -8% 0px' });
  items.forEach((el) => observer.observe(el));
}

export function initYear() {
  const el = document.querySelector('[data-year]');
  if (el) el.textContent = new Date().getFullYear();
}
