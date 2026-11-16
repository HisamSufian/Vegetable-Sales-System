// Service worker for the Sufi Vegetable Sales System.
// It only makes the site installable on a phone. It NEVER stores pages or data:
// every request goes straight to the network, so you always see live numbers.
// If the phone has no connection, it shows a short message instead of a browser error.

var OFFLINE_PAGE =
  '<!doctype html><html lang="en"><head><meta charset="utf-8">' +
  '<meta name="viewport" content="width=device-width, initial-scale=1">' +
  '<title>No connection</title></head>' +
  '<body style="font-family:system-ui,sans-serif;text-align:center;padding:40px 20px">' +
  '<h1>No connection</h1><p>Please check your internet and try again.</p>' +
  '<p><button style="font-size:18px;padding:12px 24px" onclick="location.reload()">Try again</button></p>' +
  '</body></html>';

self.addEventListener("install", function () { self.skipWaiting(); });
self.addEventListener("activate", function (event) { event.waitUntil(self.clients.claim()); });

self.addEventListener("fetch", function (event) {
  if (event.request.mode === "navigate") {
    event.respondWith(
      fetch(event.request).catch(function () {
        return new Response(OFFLINE_PAGE, {
          status: 503,
          headers: { "Content-Type": "text/html; charset=utf-8" }
        });
      })
    );
  }
  // Everything else is not touched: it goes to the network as usual.
});
