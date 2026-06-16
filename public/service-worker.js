// Service Worker - MLB Predictor PWA
const CACHE_NAME = "mlb-predictor-v1";
const ASSETS = [
  "./index.html",
  "./icon-192.png",
  "./icon-512.png",
  "./manifest.json",
];

// Instalar: cachear los assets base
self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS))
  );
  self.skipWaiting();
});

// Activar: limpiar caches viejos
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys.filter((k) => k !== CACHE_NAME).map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

// Fetch:
// - data.json: network-first (siempre intenta datos frescos, cae a cache si no hay red)
// - todo lo demas: cache-first (carga rapida)
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);

  if (url.pathname.endsWith("data.json")) {
    // Network-first para los datos
    event.respondWith(
      fetch(event.request)
        .then((res) => {
          const clone = res.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(event.request, clone));
          return res;
        })
        .catch(() => caches.match(event.request))
    );
  } else {
    // Cache-first para el resto
    event.respondWith(
      caches.match(event.request).then((cached) => cached || fetch(event.request))
    );
  }
});
