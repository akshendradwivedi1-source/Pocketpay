const CACHE_NAME = 'pocketpay-v1.2.0';
const STATIC_ASSETS = [
  '/',
  '/static/css/app.css',
  '/static/css/animations.css',
  '/static/css/charts.css',
  '/static/css/assistant.css',
  '/static/js/app.js',
  '/static/js/api.js',
  '/static/js/ui.js',
  '/static/js/init.js',
  '/static/js/assistant.js',
  '/static/js/views/dashboard.js',
  '/static/js/views/pockets.js',
  '/static/js/views/transactions.js',
  '/static/js/views/analytics.js',
  '/static/js/views/wallet.js',
  '/static/js/views/modals.js',
  '/static/manifest.json'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[SW] Cache prefetch skipped for non-static routes', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const url = new URL(event.request.url);

  // Network-first strategy for API and Auth requests
  if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/auth/')) {
    event.respondWith(
      fetch(event.request).catch(() => {
        return new Response(
          JSON.stringify({ success: false, error: 'Offline mode active. Reconnect to process live transactions.' }),
          { headers: { 'Content-Type': 'application/json' }, status: 503 }
        );
      })
    );
    return;
  }

  // Stale-while-revalidate for static UI assets
  event.respondWith(
    caches.match(event.request).then((cachedResponse) => {
      const fetchPromise = fetch(event.request).then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200 && networkResponse.type === 'basic') {
          const responseToCache = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, responseToCache));
        }
        return networkResponse;
      }).catch(() => cachedResponse);

      return cachedResponse || fetchPromise;
    })
  );
});
