(function () {
  if (!("serviceWorker" in navigator)) {
    return;
  }

  window.addEventListener("load", function () {
    navigator.serviceWorker.register("/frontend/pwa-sw.js", { scope: "/frontend/" }).catch(function () {
      // Installation is a browser enhancement; the portal must keep working without it.
    });
  });
})();
