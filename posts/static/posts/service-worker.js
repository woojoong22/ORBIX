const ORBIX_CACHE = "orbix-pwa-v1";
const ORBIX_STATIC_ASSETS = [
  "/",
  "/home/",
  "/static/posts/orbix.css",
  "/static/posts/orbix-logo.png",
  "/manifest.webmanifest"
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(ORBIX_CACHE).then((cache) => cache.addAll(ORBIX_STATIC_ASSETS))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((key) => key !== ORBIX_CACHE).map((key) => caches.delete(key)))
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  if (request.method !== "GET") {
    return;
  }

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) {
    return;
  }

  if (request.mode === "navigate") {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone();
          caches.open(ORBIX_CACHE).then((cache) => cache.put(request, copy));
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || caches.match("/home/")))
    );
    return;
  }

  event.respondWith(
    caches.match(request).then((cached) => {
      if (cached) {
        return cached;
      }
      return fetch(request).then((response) => {
        if (response.ok && (url.pathname.startsWith("/static/") || url.pathname.startsWith("/media/"))) {
          const copy = response.clone();
          caches.open(ORBIX_CACHE).then((cache) => cache.put(request, copy));
        }
        return response;
      });
    })
  );
});
