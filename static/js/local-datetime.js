/**
 * Affiche les <time class="js-local-datetime" datetime="...Z"> en heure locale
 * du navigateur (fuseau et locale de l’utilisateur).
 */
(function () {
  function formatLocal(el) {
    var iso = el.getAttribute("datetime");
    if (!iso) return;
    var d = new Date(iso);
    if (Number.isNaN(d.getTime())) return;
    var lang = document.documentElement.lang || undefined;
    el.textContent = d.toLocaleString(lang, {
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  }

  function run() {
    document.querySelectorAll("time.js-local-datetime").forEach(formatLocal);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", run);
  } else {
    run();
  }
})();
