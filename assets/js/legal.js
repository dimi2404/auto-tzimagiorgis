/* Rechtliche Seiten: Kontaktdaten aus site.json einsetzen. */
import { loadSite, initHeader, initYear } from './site.js';

initHeader();
initYear();
loadSite().catch((error) => console.error(error));
