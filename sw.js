/* Pitlane Lab : service worker (réseau d'abord pour le contenu, cache pour le reste, repli hors ligne) */
const V = 'pitlane-lab-v4';
const CORE = ['./', 'index.html', 'content.json', 'images/logo-full.png', 'images/car-lines.png', 'fonts/saira-italic.woff2', 'fonts/barlow-400.woff2', 'fonts/barlow-500.woff2', 'fonts/barlow-600.woff2', 'fonts/barlow-700.woff2'];
self.addEventListener('install', e => { e.waitUntil(caches.open(V).then(c => Promise.allSettled(CORE.map(u => c.add(u)))).then(() => self.skipWaiting())); });
self.addEventListener('activate', e => { e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== V).map(k => caches.delete(k)))).then(() => self.clients.claim())); });
self.addEventListener('fetch', e => {
  const r = e.request; if (r.method !== 'GET' || r.cache === 'no-store' || r.cache === 'reload') return;   // l'admin vérifie toujours le réseau
  const u = new URL(r.url); if (u.origin !== location.origin || /admin/.test(u.pathname)) return;
  const fresh = r.mode === 'navigate' || /content\.json$/.test(u.pathname) || /\.(html|webmanifest)$/.test(u.pathname);
  if (fresh){
    e.respondWith(fetch(r).then(res => { if (res.ok){ const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); } return res; }).catch(() => caches.match(r).then(m => m || caches.match('index.html') || caches.match('./'))));
  } else {
    e.respondWith(caches.match(r).then(m => { const net = fetch(r).then(res => { if (res.ok){ const cp = res.clone(); caches.open(V).then(c => c.put(r, cp)); } return res; }).catch(() => m); return m || net; }));
  }
});
