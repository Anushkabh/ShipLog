/*!
 * Shiplog "What's new" widget — a zero-dependency, single-file embeddable.
 *
 * Embed:
 *   <script src="https://your-api/widget.js" data-key="PUBLIC_KEY" async></script>
 *
 * It renders a floating launcher with an unread badge; clicking it opens a
 * popover of recent releases pulled from the public feed. Everything lives in a
 * Shadow DOM so the host page's CSS can never touch it and vice-versa.
 *
 * Config (data-* on the script tag):
 *   data-key       (required)  the project's public key
 *   data-api       (optional)  API origin; defaults to the origin this script loaded from
 *   data-accent    (optional)  brand color for the launcher/links (default #6366f1)
 *   data-position  (optional)  bottom-right | bottom-left (default bottom-right)
 *   data-trigger   (optional)  CSS selector of YOUR element to open the panel from
 *                              (when set, no floating launcher is rendered)
 *
 * bodyHtml from the feed is already sanitized server-side (nh3 allowlist) at
 * write time, so it is injected verbatim.
 */
(function () {
  "use strict";

  var script = document.currentScript;
  if (!script) return; // needs a script context to read config

  var KEY = script.getAttribute("data-key");
  if (!KEY) {
    console.warn("[shiplog] widget: missing data-key, not initializing.");
    return;
  }

  // Default the API origin to wherever this script was served from.
  var API = (script.getAttribute("data-api") || new URL(script.src).origin).replace(/\/$/, "");
  var ACCENT = script.getAttribute("data-accent") || "#6366f1";
  var POSITION = script.getAttribute("data-position") || "bottom-right";
  var TRIGGER_SEL = script.getAttribute("data-trigger");
  var SEEN_KEY = "shiplog:" + KEY + ":seen";

  var state = { feed: null, open: false, mounted: false };

  // ── Data ──────────────────────────────────────────────────────────────
  function fetchFeed() {
    return fetch(API + "/api/v1/widget/" + KEY + "/feed", { credentials: "omit" })
      .then(function (r) { return r.json(); })
      .catch(function () { return { releases: [], siteUrl: "#" }; });
  }

  function trackView(releaseId) {
    // Fire-and-forget; failures are irrelevant to the reader.
    try {
      fetch(API + "/api/v1/widget/" + KEY + "/view/" + releaseId, {
        method: "POST",
        credentials: "omit",
        keepalive: true,
      });
    } catch (e) { /* ignore */ }
  }

  function lastSeen() {
    try { return localStorage.getItem(SEEN_KEY) || ""; } catch (e) { return ""; }
  }
  function markSeen(iso) {
    try { localStorage.setItem(SEEN_KEY, iso); } catch (e) { /* private mode */ }
  }

  function unreadCount() {
    if (!state.feed) return 0;
    var seen = lastSeen();
    return state.feed.releases.filter(function (r) {
      return !seen || new Date(r.publishedAt) > new Date(seen);
    }).length;
  }

  // ── Helpers ───────────────────────────────────────────────────────────
  function relTime(iso) {
    var d = new Date(iso), now = new Date();
    var days = Math.floor((now - d) / 86400000);
    if (days <= 0) return "today";
    if (days === 1) return "yesterday";
    if (days < 30) return days + " days ago";
    if (days < 60) return "a month ago";
    if (days < 365) return Math.floor(days / 30) + " months ago";
    return d.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  }

  function el(tag, attrs, html) {
    var e = document.createElement(tag);
    if (attrs) Object.keys(attrs).forEach(function (k) { e.setAttribute(k, attrs[k]); });
    if (html != null) e.innerHTML = html;
    return e;
  }

  // ── Styles (scoped to the shadow root) ────────────────────────────────
  function styles() {
    return (
      ":host{all:initial}" +
      "*{box-sizing:border-box;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif}" +
      ".launcher{position:fixed;z-index:2147483000;bottom:20px;display:inline-flex;align-items:center;gap:8px;" +
      "padding:10px 14px;border:0;border-radius:999px;background:" + ACCENT + ";color:#fff;font-size:14px;font-weight:600;" +
      "cursor:pointer;box-shadow:0 6px 20px rgba(0,0,0,.18);transition:transform .12s ease}" +
      ".launcher:hover{transform:translateY(-1px)}" +
      ".right{right:20px}.left{left:20px}" +
      ".dot{position:absolute;top:-4px;right:-4px;min-width:18px;height:18px;padding:0 5px;border-radius:999px;" +
      "background:#ef4444;color:#fff;font-size:11px;font-weight:700;display:flex;align-items:center;justify-content:center;border:2px solid #fff}" +
      ".panel{position:fixed;z-index:2147483000;bottom:78px;width:380px;max-width:calc(100vw - 32px);max-height:min(560px,80vh);" +
      "display:flex;flex-direction:column;background:#fff;color:#0f172a;border-radius:16px;overflow:hidden;" +
      "box-shadow:0 16px 48px rgba(0,0,0,.24);border:1px solid rgba(0,0,0,.06)}" +
      ".panel.right{right:20px}.panel.left{left:20px}" +
      ".hd{display:flex;align-items:center;justify-content:space-between;padding:16px 18px;border-bottom:1px solid #eef0f3}" +
      ".hd h3{margin:0;font-size:15px;font-weight:700}" +
      ".x{border:0;background:transparent;cursor:pointer;color:#64748b;font-size:20px;line-height:1;padding:2px 6px;border-radius:6px}" +
      ".x:hover{background:#f1f5f9}" +
      ".list{overflow-y:auto;padding:4px 0}" +
      ".item{padding:14px 18px;border-bottom:1px solid #f1f5f9}" +
      ".item:last-child{border-bottom:0}" +
      ".item .top{display:flex;align-items:baseline;justify-content:space-between;gap:10px}" +
      ".item a.title{color:#0f172a;font-weight:700;font-size:14.5px;text-decoration:none}" +
      ".item a.title:hover{color:" + ACCENT + "}" +
      ".item .time{color:#94a3b8;font-size:12px;white-space:nowrap}" +
      ".tags{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0 2px}" +
      ".tag{font-size:11px;font-weight:600;padding:2px 8px;border-radius:999px;color:#fff}" +
      ".body{margin-top:6px;font-size:13.5px;line-height:1.55;color:#334155}" +
      ".body h1,.body h2,.body h3{font-size:14px;margin:10px 0 4px}" +
      ".body ul{margin:6px 0;padding-left:18px}.body li{margin:2px 0}" +
      ".body p{margin:6px 0}.body a{color:" + ACCENT + "}" +
      ".empty{padding:32px 18px;text-align:center;color:#94a3b8;font-size:14px}" +
      ".ft{padding:12px 18px;border-top:1px solid #eef0f3;text-align:center}" +
      ".ft a{color:" + ACCENT + ";font-size:13px;font-weight:600;text-decoration:none}" +
      "@media (prefers-color-scheme:dark){" +
      ".panel{background:#0f172a;color:#e2e8f0;border-color:rgba(255,255,255,.08)}" +
      ".hd{border-color:#1e293b}.item{border-color:#1e293b}" +
      ".item a.title{color:#e2e8f0}.body{color:#cbd5e1}.x:hover{background:#1e293b}" +
      ".hd h3{color:#f1f5f9}.ft{border-color:#1e293b}}"
    );
  }

  // ── Render ────────────────────────────────────────────────────────────
  var root, host;

  function ensureHost() {
    if (host) return;
    host = document.createElement("div");
    host.id = "shiplog-widget";
    document.body.appendChild(host);
    root = host.attachShadow({ mode: "open" });
    root.appendChild(el("style", null, styles()));
  }

  function side() { return POSITION === "bottom-left" ? "left" : "right"; }

  function renderLauncher() {
    if (TRIGGER_SEL) return; // host provides its own trigger
    var old = root.querySelector(".launcher");
    if (old) old.remove();
    var b = el("button", { class: "launcher " + side(), "aria-label": "What's new" });
    b.innerHTML =
      '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/></svg>' +
      "<span>What's new</span>";
    var n = unreadCount();
    if (n > 0) b.appendChild(el("span", { class: "dot" }, n > 9 ? "9+" : String(n)));
    b.addEventListener("click", toggle);
    root.appendChild(b);
  }

  function renderPanel() {
    var existing = root.querySelector(".panel");
    if (existing) existing.remove();
    if (!state.open) return;

    var panel = el("div", { class: "panel " + side(), role: "dialog", "aria-label": "What's new" });
    var hd = el("div", { class: "hd" });
    hd.appendChild(el("h3", null, "What&rsquo;s new"));
    var x = el("button", { class: "x", "aria-label": "Close" }, "&times;");
    x.addEventListener("click", close);
    hd.appendChild(x);
    panel.appendChild(hd);

    var releases = (state.feed && state.feed.releases) || [];
    if (!releases.length) {
      panel.appendChild(el("div", { class: "empty" }, "No updates yet — check back soon."));
    } else {
      var list = el("div", { class: "list" });
      releases.forEach(function (r) {
        var item = el("div", { class: "item" });
        var top = el("div", { class: "top" });
        var a = el("a", { class: "title", href: r.url, target: "_blank", rel: "noopener" });
        a.textContent = r.title;
        top.appendChild(a);
        top.appendChild(el("span", { class: "time" }, relTime(r.publishedAt)));
        item.appendChild(top);
        if (r.tags && r.tags.length) {
          var tags = el("div", { class: "tags" });
          r.tags.forEach(function (t) {
            var chip = el("span", { class: "tag", style: "background:" + (t.color || ACCENT) });
            chip.textContent = t.name;
            tags.appendChild(chip);
          });
          item.appendChild(tags);
        }
        item.appendChild(el("div", { class: "body" }, r.bodyHtml || ""));
        list.appendChild(item);
      });
      panel.appendChild(list);
      var site = (state.feed && state.feed.siteUrl) || "#";
      if (site && site !== "#") {
        var ft = el("div", { class: "ft" });
        var all = el("a", { href: site, target: "_blank", rel: "noopener" }, "See all updates →");
        ft.appendChild(all);
        panel.appendChild(ft);
      }
    }
    root.appendChild(panel);
  }

  // ── Behaviour ─────────────────────────────────────────────────────────
  function toggle() { state.open ? close() : openPanel(); }

  function openPanel() {
    state.open = true;
    renderPanel();
    var releases = (state.feed && state.feed.releases) || [];
    if (releases.length) {
      markSeen(releases[0].publishedAt); // newest first
      if (releases[0].id) trackView(releases[0].id);
    }
    renderLauncher(); // clears the unread dot
    setTimeout(function () { document.addEventListener("click", outside, true); }, 0);
    document.addEventListener("keydown", onKey);
  }

  function close() {
    state.open = false;
    renderPanel();
    document.removeEventListener("click", outside, true);
    document.removeEventListener("keydown", onKey);
  }

  function outside(e) {
    // e.target is the host element when the click is inside the shadow tree.
    if (e.target !== host) close();
  }
  function onKey(e) { if (e.key === "Escape") close(); }

  function bindExternalTrigger() {
    if (!TRIGGER_SEL) return;
    var nodes = document.querySelectorAll(TRIGGER_SEL);
    nodes.forEach(function (n) { n.addEventListener("click", function (e) { e.preventDefault(); toggle(); }); });
  }

  // ── Init ──────────────────────────────────────────────────────────────
  function init() {
    ensureHost();
    fetchFeed().then(function (feed) {
      state.feed = feed;
      renderLauncher();
      bindExternalTrigger();
    });
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
