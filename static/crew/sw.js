const CACHE = 'fgk-shell-v2';
const SHELL = ['/static/crew/offline.html', '/static/css/crew.css', '/static/js/crew.js', '/static/brand/logo.jpg', '/static/crew/icon-192.png'];
self.addEventListener('install', event => { event.waitUntil(caches.open(CACHE).then(cache => cache.addAll(SHELL))); self.skipWaiting(); });
self.addEventListener('activate', event => event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('fgk-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim())));
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== 'GET') return;
  if (event.request.mode === 'navigate') {
    // Authenticated HTML, invoices, tokens and photographs are NEVER cached.
    event.respondWith(fetch(event.request).catch(() => caches.match('/static/crew/offline.html')));
  } else if (SHELL.includes(url.pathname)) {
    event.respondWith(caches.match(event.request).then(cached => cached || fetch(event.request)));
  }
});
self.addEventListener('push', event => {
  let data = {}; try { data = event.data.json(); } catch (_) {}
  const target = typeof data.url === 'string' && data.url.startsWith('/crew/') ? data.url : '/crew/notifications/';
  event.waitUntil(self.registration.showNotification('FirstGlanceKnox', {body:'You have a new work update. Open your workspace to review it.', icon:'/static/crew/icon-192.png', data:{url:target}, tag:data.tag || 'fgk-update'}));
});
self.addEventListener('notificationclick', event => { event.notification.close(); event.waitUntil(clients.openWindow(event.notification.data.url)); });
self.addEventListener('message', event => { if(event.data === 'LOGOUT') event.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('fgk-')).map(k => caches.delete(k))))); });
