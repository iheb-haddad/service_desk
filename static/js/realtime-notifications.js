/**
 * Toasts + badge : polling des nouvelles notifications (quasi temps réel).
 */
(function () {
  const body = document.body;
  const pollUrl = body.dataset.notifPollUrl;
  const countUrl = body.dataset.notifCountUrl;
  const root = document.getElementById("toast-root");
  if (!pollUrl || !root) return;

  let lastId = parseInt(body.dataset.notifCursor || "0", 10) || 0;
  const POLL_MS = 5000;
  const TOAST_MS = 9000;

  function updateSidebarCount() {
    if (!countUrl) return;
    fetch(countUrl, { credentials: "same-origin" })
      .then((r) => r.json())
      .then((data) => {
        const c = typeof data.count === "number" ? data.count : 0;
        const wrap = document.getElementById("sidebar-notif-wrap");
        if (!wrap) return;
        let pill = document.getElementById("sidebar-notif-pill");
        if (c > 0) {
          if (!pill) {
            pill = document.createElement("span");
            pill.className = "pill";
            pill.id = "sidebar-notif-pill";
            wrap.appendChild(pill);
          }
          pill.textContent = String(c);
        } else if (pill) {
          pill.remove();
        }
      })
      .catch(() => {});
  }

  function showToast(item) {
    const el = document.createElement("div");
    el.className = "toast";
    el.setAttribute("role", "status");
    el.innerHTML =
      '<button type="button" class="toast-close" aria-label="Fermer">&times;</button>' +
      '<div class="toast-title"></div>' +
      '<div class="toast-msg"></div>' +
      '<a class="toast-link" href="#">Ouvrir</a>';
    el.querySelector(".toast-title").textContent = item.titre || "Notification";
    el.querySelector(".toast-msg").textContent = item.message || "";
    const link = el.querySelector(".toast-link");
    if (item.lien) {
      link.href = item.lien;
    } else {
      link.remove();
    }
    const close = () => {
      el.classList.remove("toast-visible");
      el.classList.add("toast-out");
      setTimeout(() => el.remove(), 280);
    };
    el.querySelector(".toast-close").addEventListener("click", close);
    setTimeout(close, TOAST_MS);
    root.appendChild(el);
    requestAnimationFrame(() => el.classList.add("toast-visible"));
  }

  function poll() {
    const url = pollUrl + (pollUrl.indexOf("?") >= 0 ? "&" : "?") + "apres=" + encodeURIComponent(String(lastId));
    fetch(url, { credentials: "same-origin" })
      .then((r) => {
        if (!r.ok) throw new Error("poll");
        return r.json();
      })
      .then((data) => {
        const items = data.items || [];
        let changed = false;
        for (const it of items) {
          showToast(it);
          lastId = Math.max(lastId, it.id);
          changed = true;
        }
        if (changed) updateSidebarCount();
      })
      .catch(() => {});
  }

  setInterval(poll, POLL_MS);
})();
