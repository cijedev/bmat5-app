/* Better Mental Wellness — installability service worker.
   v2 (Oct 2026, new app icon). Pass-through only. Does not cache HTML, API, auth, CSRF, or Socket.IO. */
self.addEventListener("install", (event) => {
  event.waitUntil(self.skipWaiting());
});

self.addEventListener("activate", (event) => {
  event.waitUntil(self.clients.claim());
});

self.addEventListener("fetch", () => {
  /* Empty handler: required for Chrome installability.
     Not calling respondWith leaves every request on the network. */
});
