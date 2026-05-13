/* ЧитАИ — service worker (минимальный, demo-режим).
 *
 * Стратегия:
 *  - precache статической оболочки приложения;
 *  - network-first для запросов к API (`/api/...`) с fallback на пустой JSON;
 *  - stale-while-revalidate для прочих GET-запросов.
 * Запросы с куки/конфиденциальные методы (POST/PUT/DELETE) не кешируются.
 */

const VERSION = "v1";
const SHELL_CACHE = `chitai-shell-${VERSION}`;
const ASSET_CACHE = `chitai-assets-${VERSION}`;

const SHELL_FILES = [
  "/",
  "/index.html",
  "/manifest.webmanifest",
  "/icons/icon-192.svg",
  "/icons/icon-512.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(SHELL_CACHE).then((cache) => cache.addAll(SHELL_FILES))
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((k) => ![SHELL_CACHE, ASSET_CACHE].includes(k))
          .map((k) => caches.delete(k))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  if (req.method !== "GET") return;

  const url = new URL(req.url);
  if (url.origin !== self.location.origin) return;

  if (url.pathname.startsWith("/api/")) {
    event.respondWith(
      fetch(req).catch(() =>
        new Response(JSON.stringify({ offline: true }), {
          status: 503,
          headers: { "content-type": "application/json; charset=utf-8" },
        })
      )
    );
    return;
  }

  event.respondWith(
    caches.match(req).then((cached) => {
      const fetchPromise = fetch(req)
        .then((res) => {
          if (res && res.ok) {
            const clone = res.clone();
            caches.open(ASSET_CACHE).then((cache) => cache.put(req, clone));
          }
          return res;
        })
        .catch(() => cached);
      return cached || fetchPromise;
    })
  );
});
