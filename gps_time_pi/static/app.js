/* Theme must already be applied by the inline <head> snippet before this
   file loads; here we just wire the buttons and shared helpers. */

function wireThemes() {
  const cur = document.documentElement.dataset.theme || "light";
  document.querySelectorAll("nav .themes button").forEach(b => {
    b.classList.toggle("on", b.dataset.t === cur);
    b.onclick = () => {
      localStorage.setItem("gtp-theme", b.dataset.t);
      document.documentElement.dataset.theme = b.dataset.t;
      document.querySelectorAll("nav .themes button")
        .forEach(x => x.classList.toggle("on", x === b));
    };
  });
}

function getTZ() {
  const saved = localStorage.getItem("gtp-tz");
  if (saved) return saved;
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC"; }
  catch (e) { return "UTC"; }
}

function wireTZ(sel, onchange) {
  (Intl.supportedValuesOf ? Intl.supportedValuesOf("timeZone") : ["UTC"])
    .concat(["UTC"]).sort().forEach(z => {
      const o = document.createElement("option");
      o.value = o.textContent = z;
      sel.appendChild(o);
    });
  sel.value = getTZ();
  sel.onchange = () => { localStorage.setItem("gtp-tz", sel.value); onchange(sel.value); };
}

/* server-time estimator: trust the lowest-RTT sample */
const clockEst = { offset: null, bestRtt: Infinity };
function feedClock(epochMs, rttMs) {
  const sample = epochMs + rttMs / 2 - Date.now();
  if (clockEst.offset === null || rttMs < clockEst.bestRtt ||
      Math.abs(sample - clockEst.offset) > 50) {
    clockEst.offset = sample; clockEst.bestRtt = rttMs;
  }
}
function serverNow() {
  return clockEst.offset === null ? null : new Date(Date.now() + clockEst.offset);
}
function pad(n, w) { return String(n).padStart(w, "0"); }

function fmtClock(d, tz) {
  let h = "--", m = "--", s = "--";
  try {
    new Intl.DateTimeFormat("en-GB", { hour12: false, hour: "2-digit",
      minute: "2-digit", second: "2-digit", timeZone: tz })
      .formatToParts(d).forEach(p => {
        if (p.type === "hour") h = p.value === "24" ? "00" : p.value;
        if (p.type === "minute") m = p.value;
        if (p.type === "second") s = p.value;
      });
  } catch (e) { }
  return { h, m, s, ms: pad(d.getUTCMilliseconds(), 3) };
}

function localTime(iso) {
  if (!iso) return "–";
  return new Date(iso).toLocaleTimeString(undefined,
    { hour: "numeric", minute: "2-digit", timeZone: getTZ() });
}

// Demo-mode label on every page that loads this file (review GPS-019): in demo
// mode all values are fixtures, so say so above the page content.
(function demoBanner() {
  fetch("/api/auth", { cache: "no-store" }).then(r => r.json()).then(a => {
    if (!a || !a.demo || document.getElementById("gtp-demo-banner")) return;
    const d = document.createElement("div");
    d.id = "gtp-demo-banner";
    d.textContent = "SAMPLE DATA — demo mode. All values are synthetic, not measurements.";
    d.style.cssText = "margin:0 0 12px;padding:6px 10px;border:1px solid #b07810;color:#b07810;font:12px monospace;border-radius:2px";
    const main = document.querySelector("main") || document.body;
    main.insertBefore(d, main.firstChild);
  }).catch(() => {});
})();
