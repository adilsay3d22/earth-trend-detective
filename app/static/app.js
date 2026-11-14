// Earth Trend Detective front end: Cesium globe playing NASA GIBS layers year by year,
// synced to the trend analysis of the clicked region. Talks only to our backend + public GIBS tiles.
"use strict";

const $ = (id) => document.getElementById(id);
const MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];
const DOMAINS = { heat: "Heat", water: "Water", ice: "Ice", air: "Air", life: "Life" };
const SEC_PER_YEAR = 365.25 * 86400;
const GIBS = "https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/";
// GIBS geographic tiles: 512 px, level 0 = two 288-degree tiles, so the grid spans -180..396 lon, 90..-198 lat.
const GIBS_SCHEME = new Cesium.GeographicTilingScheme({
  rectangle: Cesium.Rectangle.fromDegrees(-180, -198, 396, 90), numberOfLevelZeroTilesX: 2, numberOfLevelZeroTilesY: 1,
});
const WORLD = Cesium.Rectangle.fromDegrees(-180, -90, 180, 90);

function gibs(layer, tms, maxLevel, ext, times, clock) {
  return new Cesium.WebMapTileServiceImageryProvider({
    url: `${GIBS}${layer}/default/${times ? "{Time}/" : ""}{TileMatrixSet}/{TileMatrix}/{TileRow}/{TileCol}.${ext}`,
    layer, style: "default", tileMatrixSetID: tms, tilingScheme: GIBS_SCHEME, rectangle: WORLD,
    maximumLevel: maxLevel, tileWidth: 512, tileHeight: 512, times, clock,
  });
}

const viewer = new Cesium.Viewer("globe", {
  baseLayer: new Cesium.ImageryLayer(gibs("BlueMarble_ShadedRelief_Bathymetry", "500m", 7, "jpeg")),
  terrainProvider: new Cesium.EllipsoidTerrainProvider(),
  sceneMode: Cesium.SceneMode.SCENE2D,       // flat map like Worldview by default; button switches to the 3D globe
  baseLayerPicker: false, geocoder: false, homeButton: false, sceneModePicker: false, navigationHelpButton: false,
  animation: false, timeline: false, fullscreenButton: false, infoBox: false, selectionIndicator: false,
});
// data colours must match NASA's legend: no atmospheric haze or lighting on the ground
viewer.scene.globe.showGroundAtmosphere = false;
viewer.scene.globe.enableLighting = false;
viewer.scene.fog.enabled = false;
viewer.scene.backgroundColor = Cesium.Color.fromCssColorString("#0e0f11");
const ACCENT = "#e5b84f";                   // keep in sync with --accent in style.css
// Overlays above the data: borders/roads (GIBS draws them only when zoomed in) and coastlines (every zoom),
// darkened so they read on every colour scale.
// (GIBS Reference_Features/Labels are blank PNGs at these zooms, so borders and names come from Natural Earth below.)
const coast = viewer.imageryLayers.addImageryProvider(gibs("Coastlines_15m", "15.625m", 12, "png"));
coast.brightness = 0.2;

// ---------- where am I: Natural Earth borders + country and city names (public domain, ships with the app) ----------
const LIFT = 3000;                          // metres above the surface so lines/labels don't flicker on the 3D globe
const lifted = (lonLat) => {
  const out = [];
  for (let i = 0; i < lonLat.length; i += 2) out.push(lonLat[i], lonLat[i + 1], LIFT);
  return Cesium.Cartesian3.fromDegreesArrayHeights(out);
};
const borderLines = viewer.scene.primitives.add(new Cesium.PolylineCollection());
const placeLabels = viewer.scene.primitives.add(new Cesium.LabelCollection());
const eventDots = viewer.scene.primitives.add(new Cesium.PointPrimitiveCollection());
const places = [];                          // [label, show while the view is narrower than this many metres]
fetch("places.json").then((r) => r.json()).then((p) => {
  const lineMat = Cesium.Material.fromType("Color", { color: Cesium.Color.fromCssColorString("#111").withAlpha(0.6) });
  for (const b of p.borders) borderLines.add({ positions: lifted(b), width: 1, material: lineMat });
  const add = (text, lon, lat, font, maxWidth, city) => places.push([placeLabels.add({
    position: Cesium.Cartesian3.fromDegrees(lon, lat, LIFT), text: city ? "• " + text : text, font,
    fillColor: city ? Cesium.Color.WHITE : Cesium.Color.WHITE.withAlpha(0.85), outlineColor: Cesium.Color.BLACK,
    outlineWidth: 3, style: Cesium.LabelStyle.FILL_AND_OUTLINE, show: false,
    horizontalOrigin: city ? Cesium.HorizontalOrigin.LEFT : Cesium.HorizontalOrigin.CENTER,
    verticalOrigin: Cesium.VerticalOrigin.CENTER, pixelOffset: new Cesium.Cartesian2(city ? -4 : 0, 0),
  }), maxWidth]);
  for (const [n, lon, lat, rank] of p.countries) {
    add(n.toUpperCase(), lon, lat, "600 12px system-ui, sans-serif", rank <= 2 ? 5e7 : rank <= 3 ? 2.6e7 : rank <= 4 ? 1.6e7 : 9e6);
  }
  for (const [n, lon, lat, rank] of p.cities) add(n, lon, lat, "12px system-ui, sans-serif", [1.2e7, 8e6, 5e6, 3e6, 1.8e6][rank] ?? 1e6, true);
  updatePlaces();
});

function viewWidth() {                      // metres across the view
  const c = viewer.camera;
  return is2D() ? c.frustum.right - c.frustum.left : c.positionCartographic.height * 1.2;
}
function updatePlaces() {                   // more names appear as you zoom in
  const w = viewWidth();
  for (const [label, maxWidth] of places) label.show = w < maxWidth;
}
viewer.camera.percentageChanged = 0.05;
viewer.camera.changed.addEventListener(updatePlaces);

// Coarse grids (e.g. MERRA-2 0.5 deg = ~55 km) are drawn smoothly: tiles stop at the data's own resolution and Cesium
// blends between grid cells instead of blowing pixels up into blocks. GIBS level 0 = 0.5625 deg per pixel.
const GRID_DEG = [[/^MERRA2_/, 0.5], [/^AIRS_/, 1], [/^CERES_/, 1],[/^GLDAS_/, 0.25], [/^OMI_/, 0.25], [/^SMAP_L3_Sea_Surface/, 0.25]];
const gridDeg = (layer) => (GRID_DEG.find(([re]) => re.test(layer)) || [])[1];
const smoothLevel = (look) => gridDeg(look.layer) ? Math.min(look.max_level, Math.ceil(Math.log2(0.5625 / gridDeg(look.layer)))) : look.max_level;

// Gentle, bounded navigation: small wheel steps, little drift, no tilting, can't fly off into space.
// In 2D Cesium measures zoom as map width, in 3D as camera height, so the limits differ per mode.
const HOME = [10, 35, 1.6e7];
const LIMITS = { "2d": [6e5, 4.5e7], "3d": [3e5, 2.5e7] };
const nav = viewer.scene.screenSpaceCameraController;
nav.zoomFactor = 1.5;                       // Cesium default 5
nav.inertiaZoom = 0.3;
nav.inertiaSpin = 0.6;
nav.inertiaTranslate = 0.6;
nav.enableTilt = false;
nav.enableLook = false;
const is2D = () => viewer.scene.mode === Cesium.SceneMode.SCENE2D;
const limits = () => LIMITS[is2D() ? "2d" : "3d"];

function goHome(duration = 0.8) {
  [nav.minimumZoomDistance, nav.maximumZoomDistance] = limits();
  viewer.camera.flyTo({ duration, destination: is2D() ? Cesium.Rectangle.fromDegrees(-180, -90, 180, 90)
    : Cesium.Cartesian3.fromDegrees(...HOME) });
}
goHome(0);

function zoomBy(factor) {                   // factor < 1 zooms in, > 1 zooms out
  const cam = viewer.camera, [lo, hi] = limits();
  if (is2D()) {
    const w = cam.frustum.right - cam.frustum.left;
    const target = Math.min(hi, Math.max(lo, w * factor));
    if (target < w) cam.zoomIn((w - target) / 2); else cam.zoomOut((target - w) / 2);
    return;
  }
  const c = cam.positionCartographic;
  const h = Math.min(hi, Math.max(lo, c.height * factor));
  cam.flyTo({ destination: Cesium.Cartesian3.fromRadians(c.longitude, c.latitude, h), duration: 0.4 });
}

function setFlat(flat) {
  if (flat) viewer.scene.morphTo2D(0); else viewer.scene.morphTo3D(0);
  goHome(0);
  updatePlaces();
  $("mode").textContent = flat ? "3D" : "2D";
  $("mode").title = $("mode").ariaLabel = flat ? "Switch to 3D globe" : "Switch to flat map";
}

const state = { vars: {}, v: null, dataLayer: null, y0: 2000, y1: 2026, scope: null, lat: 0, lon: 0, trend: null, box: null };

// ---------- variable list ----------
fetch("/api/variables").then((r) => r.json()).then((vars) => {
  const sel = $("variable");
  for (const [d, label] of Object.entries(DOMAINS)) {
    const g = document.createElement("optgroup");
    g.label = label;
    for (const v of vars.filter((x) => x.domain === d)) {
      state.vars[v.id] = v;
      g.append(new Option(v.name + (v.look ? "" : " (chart only)"), v.id));
    }
    sel.append(g);
  }
  sel.value = "air_temp";
  selectVariable();
});

function layerYears(look, month) {
  // first/last year that has an image for the chosen month
  const [sy, sm] = look.start.split("-").map(Number);
  const [ey, em] = look.end.split("-").map(Number);
  return [sy + (sm > month ? 1 : 0), ey - (em < month ? 1 : 0)];
}

function mapMonth() {
  return Number($("month").value) || state.v.look?.month || 7;
}

function selectVariable() {
  state.v = state.vars[$("variable").value];
  const v = state.v;
  $("plain").textContent = v.plain || "";
  $("note").hidden = !(v.look?.note || !v.look);
  $("note").textContent = v.look ? v.look.note || "" : "No NASA map layer for this variable yet: chart only.";
  $("global").hidden = !v.global;
  $("legend").innerHTML = v.look?.legend ? `<img src="${v.look.legend}" alt="Colour legend for the map">` : "";
  $("hint").textContent = v.box ? "Click a spot on the globe to investigate it. Drag to move, scroll or +/− to zoom." :
    v.global ? "This variable is measured for the whole Earth or a hemisphere." : "Numbers for this variable are not wired up yet.";
  if (v.look) {
    const [a, b] = layerYears(v.look, mapMonth());
    $("from").value = Math.max(a, Math.min(Number($("from").value) || 2000, b - 5));
    $("to").value = b;
  } else {
    $("from").value = Number($("from").value) || 2000;
    $("to").value = Number($("to").value) || 2026;
  }
  buildTimeline();
  if (v.global && !v.box) investigate("global", state.lat || 70, 0);
  else if (state.scope === "box" && v.box) investigate("box", state.lat, state.lon);
  else if (v.global) investigate("global", state.lat || 70, 0);
  else clearResults();
}

// ---------- time-lapse ----------
function buildTimeline() {
  const v = state.v;
  if (state.dataLayer) viewer.imageryLayers.remove(state.dataLayer);
  state.dataLayer = null;
  const month = mapMonth();
  let y0 = Number($("from").value), y1 = Number($("to").value);
  if (v.look) {
    const [a, b] = layerYears(v.look, month);
    y0 = Math.max(a, Math.min(y0, b));
    y1 = Math.min(b, Math.max(y1, y0));
    $("from").value = y0;
    $("to").value = y1;
    const daily = v.look.period === "P1D";
    const times = new Cesium.TimeIntervalCollection();
    for (let y = y0; y <= y1; y++) {
      times.addInterval(new Cesium.TimeInterval({
        start: Cesium.JulianDate.fromIso8601(`${y}-01-01T00:00:00Z`),
        stop: Cesium.JulianDate.fromIso8601(`${y + 1}-01-01T00:00:00Z`), isStopIncluded: false,
        data: { Time: `${y}-${String(month).padStart(2, "0")}-${daily ? "15" : "01"}` },
      }));
    }
    const p = gibs(v.look.layer, v.look.tms, Math.max(0, smoothLevel(v.look)), v.look.format, times, viewer.clock);
    state.dataLayer = viewer.imageryLayers.addImageryProvider(p, viewer.imageryLayers.indexOf(coast));
    state.dataLayer.alpha = Number($("opacity").value);
  }
  const g = v.look && gridDeg(v.look.layer);
  $("res").textContent = g ? `Data grid: about ${Math.round(g * 111)} km (${g}°). The map blends smoothly between grid cells.` : "";
  state.y0 = y0;
  state.y1 = y1;
  const c = viewer.clock;
  c.startTime = Cesium.JulianDate.fromIso8601(`${y0}-01-01T00:00:00Z`);
  c.stopTime = Cesium.JulianDate.fromIso8601(`${y1}-12-31T00:00:00Z`);
  c.currentTime = c.startTime.clone();
  c.clockRange = Cesium.ClockRange.CLAMPED;
  c.multiplier = SEC_PER_YEAR * Number($("speed").value);
  c.shouldAnimate = false;
  $("scrub").min = y0;
  $("scrub").max = y1;
  showYear(y0);
}

function currentYear() {
  return Cesium.JulianDate.toGregorianDate(viewer.clock.currentTime).year;
}

let lastYear = null;
viewer.clock.onTick.addEventListener((c) => {
  if (!state.v) return;                      // variables not loaded yet
  const y = currentYear();
  if (y !== lastYear) showYear(y);
  if (c.shouldAnimate && Cesium.JulianDate.greaterThanOrEquals(c.currentTime, c.stopTime)) setPlaying(false);
});

function setPlaying(on) {
  const c = viewer.clock;
  if (on && Cesium.JulianDate.greaterThanOrEquals(c.currentTime, c.stopTime)) c.currentTime = c.startTime.clone();
  c.shouldAnimate = on;
  $("play").classList.toggle("on", on);
  $("play").setAttribute("aria-label", on ? "Pause" : "Play");
}

function seekYear(y) {
  y = Math.max(state.y0, Math.min(state.y1, y));
  viewer.clock.currentTime = Cesium.JulianDate.fromIso8601(`${y}-07-01T00:00:00Z`);
  showYear(y);
}

function showYear(y) {
  lastYear = y;
  const v = state.v;
  $("date").textContent = v.look ? `${MONTHS[mapMonth() - 1]} ${y}` : String(y);
  $("datesub").textContent = !v.look ? "" : Number($("month").value) ? `Map and numbers: ${MONTHS[mapMonth() - 1]} of each year`
    : `Map: ${MONTHS[mapMonth() - 1]} of each year · Numbers: yearly average`;
  $("scrub").value = y;
  const t = state.trend;
  if (!t || !t.years) return;
  if (document.getElementById("chart").data) {
    Plotly.relayout("chart", { "shapes[0].x0": y, "shapes[0].x1": y });
  }
  const i = t.years.indexOf(y);
  const base = t.values[0];
  const u = t.unit ? " " + t.unit : "";
  $("counter").innerHTML = i < 0 ? `<div class="stat"><span>${y}</span><b class="muted">no value</b></div>` :
    `<div class="stat"><span>${y}</span><b>${fmt(t.values[i])}${u}</b></div>` +
    `<div class="stat"><span>Change since ${t.years[0]}</span><b>${sign(t.values[i] - base)}${fmt(t.values[i] - base)}${u}</b></div>`;
  // highlight the record fact when its year plays
  for (const li of document.querySelectorAll("#facts li, #evlist li")) li.classList.toggle("hit", li.dataset.years?.split(",").includes(String(y)));
  for (let k = 0; k < eventDots.length; k++) eventDots.get(k).show = eventDots.get(k).year <= y;   // events pile up as years play
}

const fmt = (x) => Math.abs(x) >= 100 ? x.toFixed(0) : Math.abs(x) >= 1 ? x.toFixed(2) : x.toPrecision(3);
const sign = (x) => (x > 0 ? "+" : "");

// ---------- investigate a region ----------
const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
handler.setInputAction((e) => {
  const p = viewer.camera.pickEllipsoid(e.position);
  if (!p) return;
  const c = Cesium.Cartographic.fromCartesian(p);
  const lat = Cesium.Math.toDegrees(c.latitude), lon = Cesium.Math.toDegrees(c.longitude);
  investigate(state.v.box ? "box" : "global", lat, lon);
}, Cesium.ScreenSpaceEventType.LEFT_CLICK);

function clearResults(keepVerdict = false) {
  state.trend = null;
  $("csv").disabled = true;
  $("pin").disabled = !state.pin;
  $("compare").hidden = true;
  for (const id of ["counter", "facts", "warnings", "details", "source"]) $(id).innerHTML = "";
  for (const id of ["story", "numbers", "events", "science", "steady", "witness", "checkup", "coach"]) $(id).hidden = true;
  eventDots.removeAll();
  drawCells(null);
  $("verdict").hidden = !keepVerdict;
  $("panel").classList.toggle("idle", !keepVerdict);
  Plotly.purge("chart");
}

function replayReveal() {                    // restart the staggered fade-in for a fresh result
  const p = $("panel");
  p.classList.remove("reveal");
  void p.offsetWidth;
  p.classList.add("reveal");
}

const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const EVENT_COLOR = { wildfires: "#ff6a3d", severeStorms: "#b48cff", floods: "#3da5ff", drought: "#d9a441", dustHaze: "#e8d3a0",
  volcanoes: "#ff3030", seaLakeIce: "#e8ffff", snow: "#ffffff", tempExtremes: "#ff4fd8", landslides: "#9b6b43" };
const RELATED = { heat: ["tempExtremes", "wildfires", "drought"], water: ["floods", "drought", "landslides", "severeStorms"],
  ice: ["seaLakeIce", "snow"], air: ["dustHaze", "wildfires", "volcanoes", "manmade"], life: ["wildfires", "drought"] };

async function loadEvents(v, t) {
  // real NASA EONET records in the same area: what happened here, shown as a list and as dots that appear as years play
  const b = t.events_box, el = $("events");
  eventDots.removeAll();
  el.hidden = !b;
  if (!b) return;
  el.innerHTML = `<h2>What happened here</h2><p class="muted">Looking up NASA's natural-event records…</p>`;
  const r = await fetch(`/api/events?s=${b[0]}&w=${b[1]}&n=${b[2]}&e=${b[3]}&start=${t.years[0]}&end=${t.years.at(-1)}`).catch(() => null);
  const evs = r?.ok ? await r.json() : null;
  if (state.trend !== t) return;             // user moved on meanwhile
  const span = `${t.years[0]} to ${t.years.at(-1)}`;
  if (!evs) { el.innerHTML = `<h2>What happened here</h2><p class="muted">NASA's event tracker did not answer. Try again in a moment.</p>`; return; }
  if (!evs.length) { el.innerHTML = `<h2>What happened here</h2><p class="muted">NASA's event tracker has no records in this area from ${span}.</p>`; return; }
  const counts = {};
  for (const e of evs) counts[e.cat] = (counts[e.cat] || 0) + 1;
  const summary = Object.entries(counts).sort((a, b) => b[1] - a[1]).map(([c, k]) => `${k} ${esc(c.toLowerCase())}`).join(", ");
  const rel = RELATED[v.domain] || [];
  const per = {};                            // at most 3 per kind, so 700 fires don't hide the storms
  const top = [...evs].sort((a, b) => (rel.includes(b.cat_id) - rel.includes(a.cat_id)) || b.date.localeCompare(a.date))
    .filter((e) => (per[e.cat_id] = (per[e.cat_id] || 0) + 1) <= 3).slice(0, 8);
  const item = (e) => {
    const name = /^https?:\/\//.test(e.url || "") ? `<a href="${esc(e.url)}" target="_blank" rel="noopener">${esc(e.title)}</a>` : esc(e.title);
    return `<li data-years="${e.date.slice(0, 4)}"><span class="dot" style="background:${EVENT_COLOR[e.cat_id] || "#aaa"}"></span>` +
      `${e.date.slice(0, 7)} · ${esc(e.cat)} · ${name}</li>`;
  };
  el.innerHTML = `<h2>What happened here</h2>
    <p>NASA's Earth Observatory Natural Event Tracker (EONET) logged <b>${evs.length} event${evs.length > 1 ? "s" : ""}</b> in this area from ${span}: ${summary}.</p>
    <ul id="evlist">${top.map(item).join("")}</ul>
    ${evs.length > top.length ? `<p class="muted">+ ${evs.length - top.length} more. All of them appear as dots on the map as the years play.</p>` : `<p class="muted">They appear as dots on the map as the years play.</p>`}
    <p class="muted">These are records of what happened, not proof that the trend caused them. Most records start around 2015 and NASA keeps adding sources, so recent years show more events partly because tracking improved. Source: <a href="https://eonet.gsfc.nasa.gov/" target="_blank" rel="noopener">NASA EONET</a>.</p>`;
  eventDots.removeAll();
  for (const e of evs) {
    const p = eventDots.add({ position: Cesium.Cartesian3.fromDegrees(e.lon, e.lat, LIFT), pixelSize: 8, outlineColor: Cesium.Color.BLACK,
      outlineWidth: 1, color: Cesium.Color.fromCssColorString(EVENT_COLOR[e.cat_id] || "#aaaaaa"), disableDepthTestDistance: Number.POSITIVE_INFINITY });
    p.year = Number(e.date.slice(0, 4));
  }
  showYear(currentYear());
}

function renderStory(v, t) {
  // plain "why it matters" from the catalog; the direction text only when there is a trend to talk about
  const st = v.story;
  $("story").hidden = !st;
  if (!st) return;
  const dir = t.slope_per_decade > 0 ? "up" : "down";
  const conv = st.convert && t.unit === st.convert.unit && t.level !== "none" ? (t.fit.at(-1) - t.fit[0]) * st.convert.factor : 0;
  $("story").innerHTML = `<h2>Why it matters</h2><p>${st.why}</p>` +
    (t.level === "none" ? "" : `<p><b>${dir === "up" ? "When it rises" : "When it falls"}:</b> ${st[dir]}</p>`) +
    (conv > 0 ? `<p class="big">${st.convert.text.replace("{x}", fmt(conv))}</p>` : "");
}

async function investigate(scope, lat, lon) {
  Object.assign(state, { scope, lat, lon });
  const v = state.v;
  const q = new URLSearchParams({ var: v.id, scope, lat: lat.toFixed(2), lon: lon.toFixed(2), size: $("size").value,
    month: $("month").value, start: $("from").value, end: $("to").value });
  $("verdict").hidden = false;
  $("panel").classList.remove("idle", "reveal");
  $("verdict").className = "card";
  $("verdict").innerHTML = `<span class="sk" style="width:32%"></span><span class="sk lg"></span><span class="sk lg" style="width:68%"></span>
    <p class="wait">Fetching NASA data. The first look at a new place can take up to a minute.</p>`;
  const r = await fetch("/api/trend?" + q);
  const t = await r.json();
  if (state.v !== v) return;                 // user switched variable meanwhile
  if (!r.ok || t.error) {
    clearResults(true);
    $("verdict").innerHTML = `<h2>${t.detail || t.error}</h2>`;
    $("source").textContent = t.source ? "Numbers: " + t.source : "";
    return;
  }
  state.trend = Object.assign(t, { var: v.id });
  $("pin").disabled = $("csv").disabled = false;
  drawBox(t.box);
  drawCells(t);
  renderCompare(t);
  $("verdict").className = "card " + t.level;
  const badge = { significant: "Clear trend", borderline: "Maybe a trend", none: "No clear trend" }[t.level];
  $("verdict").innerHTML = `<span class="badge">${badge}</span><h2>${t.verdict}</h2><p>${t.meaning}</p>`;
  renderStory(v, t);
  $("warnings").innerHTML = t.warnings.map((w) => `<li>${w}</li>`).join("");
  $("numbers").hidden = false;
  $("facts").innerHTML = t.facts.map((f) => {
    const yrs = f.startsWith("Highest year") || f.startsWith("Biggest") ? (f.match(/\b(19|20)\d{2}\b/g) || []).join(",") : "";
    return `<li data-years="${yrs}">${f}</li>`;
  }).join("");
  renderSteady(t);
  $("science").hidden = false;
  $("details").innerHTML = [...t.details, t.area_note || (t.box ? `Averaged over a ${$("size").value}° box: ${t.area.replace(/^in the box /, "")}.` : null)]
    .filter(Boolean).map((d) => `<li>${d}</li>`).join("");
  const [w, s, e, n] = t.box ? [t.box[1], t.box[0], t.box[3], t.box[2]] : [-180, -90, 180, 90];
  const wv = v.look ? `https://worldview.earthdata.nasa.gov/?v=${w},${s},${e},${n}&l=${v.look.layer},Reference_Features_15m,Coastlines_15m&t=${currentYear()}-${String(mapMonth()).padStart(2, "0")}-01` : null;
  $("source").innerHTML = `Numbers: <a href="${t.link}" target="_blank" rel="noopener">${t.source}</a>` +
    (v.look ? `<br>Map: NASA GIBS ${v.look.layer} · <a href="${wv}" target="_blank" rel="noopener">open in Worldview</a>` : "");
  drawChart(t);
  showYear(currentYear());
  replayReveal();
  loadEvents(v, t);
  if (scope === "box") loadWitness(v, t, lat, lon);
  $("checkup").hidden = scope !== "box";
  $("checkup").innerHTML = `<h2>Full check-up of this place</h2><p class="muted">Run the same tests on temperature, humid heat, rain, soil water, evaporation, sunshine and (in Bangladesh) greenness here.</p>
    <button id="runcheck" type="button">Run the check-up</button>`;
  $("runcheck").onclick = () => runCheckup(t, lat, lon);
  $("coach").hidden = false;
  $("answer").textContent = "";
  state.ask = { var: v.id, scope, lat: lat.toFixed(2), lon: lon.toFixed(2), size: $("size").value,
    month: $("month").value, start: t.years[0], end: t.years.at(-1) };
}

async function askCoach(question, answerLang = lang) {
  // the server recomputes the numbers itself and gives Claude only those; nothing from here is trusted as evidence
  const t = state.trend, el = $("answer");
  el.className = "wait";
  el.textContent = answerLang === "bn" ? "কোচ ভাবছে…" : "The coach is thinking…";
  const r = await fetch("/api/coach", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...state.ask, question, lang: answerLang }) }).catch(() => null);
  const a = r ? await r.json().catch(() => ({})) : { detail: "Could not reach the server." };
  if (state.trend !== t) return;
  el.className = r && r.ok ? "" : "err";
  el.textContent = a.answer || a.detail || "The coach could not answer.";
}

async function runCheckup(t, lat, lon) {
  const el = $("checkup");
  el.querySelector("button").disabled = true;
  el.querySelector("p").textContent = "Testing every variable here. New places can take a minute…";
  const q = new URLSearchParams({ lat: lat.toFixed(2), lon: lon.toFixed(2), size: $("size").value });
  const c = await fetch("/api/checkup?" + q).then((r) => r.json()).catch(() => null);
  if (state.trend !== t) return;
  if (!c) { el.querySelector("p").textContent = "The check-up failed. Try again in a moment."; el.querySelector("button").disabled = false; return; }
  const word = { significant: "clear", borderline: "maybe", none: "no clear trend" };
  el.innerHTML = `<h2>Full check-up: ${esc(c.region)}</h2><p class="label">${esc(c.label)}</p>${c.why.map((w) => `<p class="muted">${esc(w)}</p>`).join("")}
    <table>${c.rows.map((r) => `<tr data-var="${r.var}" class="${r.level === "significant" ? "clear" : ""}" title="Open ${esc(r.name)} here">
      <td>${esc(r.name)}</td><td>${sign(r.per_decade)}${fmt(r.per_decade)} ${esc(r.unit)}/10 yr</td><td>${word[r.level]}</td></tr>`).join("")}</table>
    <p class="muted">The label comes from fixed rules on the clear trends only (idea from team TerraBangla), never from AI. Click a row to open that variable here.</p>`;
  for (const tr of el.querySelectorAll("tr")) tr.onclick = () => { $("variable").value = tr.dataset.var; selectVariable(); };
}

async function loadWitness(v, t, lat, lon) {
  // a weather station on the ground, tested the same way: do the satellite/model numbers and the thermometer agree?
  const el = $("witness");
  el.hidden = true;
  if (!["air_temp", "air_temp_max", "air_temp_min", "precip"].includes(v.id)) return;
  el.hidden = false;
  el.innerHTML = `<h2>Second witness: a weather station</h2><p class="muted">Looking for a NOAA weather station in this box…</p>`;
  const q = new URLSearchParams({ var: v.id, lat: lat.toFixed(2), lon: lon.toFixed(2), size: $("size").value,
    month: $("month").value, start: t.years[0], end: t.years.at(-1) });
  const w = await fetch("/api/witness?" + q).then((r) => r.json()).catch(() => ({ none: "The station lookup failed." }));
  if (state.trend !== t) return;
  if (!w.years || w.error) {
    el.innerHTML = `<h2>Second witness: a weather station</h2><p class="muted">${esc(w.none || w.error || "The station lookup failed. Try again in a moment.")}</p>`;
    return;
  }
  const u = t.unit ? " " + t.unit : "";
  const same = Math.sign(w.slope_per_decade) === Math.sign(t.slope_per_decade);
  const both = w.level === "significant" && t.level === "significant";
  const verdict = both && same ? `<b class="agree">They agree:</b> both show a clear ${t.slope_per_decade > 0 ? "rise" : "fall"}.`
    : both ? `<b class="disagree">They disagree:</b> the station and NASA's numbers go in opposite directions. One of them is not telling the whole story.`
    : !same && (w.level === "significant" || t.level === "significant") ? `<b class="disagree">They disagree</b> on the direction, so be careful with this trend.`
    : `<b>No contradiction</b>, but at least one of them is not clear enough to confirm the other.`;
  el.innerHTML = `<h2>Second witness: a weather station</h2>
    <p>${verdict}</p>
    <ul><li>NASA (whole box): ${sign(t.slope_per_decade)}${fmt(t.slope_per_decade)}${u} per decade, ${t.level === "none" ? "no clear trend" : t.level === "borderline" ? "maybe" : "clear"}</li>
    <li>${esc(w.station)} (${w.km} km from the box centre, ${w.years.length} years): ${sign(w.slope_per_decade)}${fmt(w.slope_per_decade)}${u} per decade, ${w.level === "none" ? "no clear trend" : w.level === "borderline" ? "maybe" : "clear"}</li></ul>
    <p class="muted">A station measures one spot, and a box average covers thousands of km², so their values differ; compare the direction and the speed. Source: <a href="${w.link}" target="_blank" rel="noopener">${esc(w.source)}</a> (NOAA, not NASA).</p>`;
  state.witness = Object.assign(w, { for: t });
  drawChart(t);
}

function renderSteady(t) {
  // same tests on the early / middle / late thirds, then where this result sits on "significant vs big"
  const u = t.unit ? " " + t.unit : "", q = t.quadrant;
  const thirds = t.periods.map((p) => `<div class="third ${p.p < 0.05 ? "real" : ""}">${p.from}–${p.to}` +
    `<b>${sign(p.per_decade)}${fmt(p.per_decade)}${u}</b>per decade${p.p < 0.05 ? " · clear" : ""}</div>`).join("");
  const cell = (big, real, text) => `<span class="cell ${q.big === big && q.real === real ? "on" : ""}">${text}</span>`;
  $("steady").hidden = false;
  $("steady").innerHTML = `<h2>Is it steady?</h2>` +
    (t.periods.length ? `<div class="thirds">${thirds}</div><p class="muted">${t.stability}</p>` : "") +
    `<div class="quad"><span></span><span>Small change</span><span>Big change</span>
      <span>Real</span>${cell(false, true, "small but real")}${cell(true, true, "big and real")}
      <span>Not sure</span>${cell(false, false, "lost in the noise")}${cell(true, false, "big but uncertain")}</div>
    <p class="muted" style="margin-top:8px">${q.label} "Big" means the trend line moved more than single years usually jump.</p>`;
}

const CELL_UP = "#ef8f55", CELL_DOWN = "#4fa3ef";   // keep in sync with --up / --down in style.css
const cellLayer = new Cesium.CustomDataSource("cells");
viewer.dataSources.add(cellLayer);
function drawCells(t) {
  // each grid cell's own trend: clear rises and falls filled, unclear cells outlined only
  cellLayer.entities.removeAll();
  $("cellkey").hidden = !t?.cells?.length;
  if (!t?.cells) return;
  const [dy, dx] = t.cell_step;
  for (const [lat, lon, slope, p] of t.cells) {
    const clear = p < 0.05;
    cellLayer.entities.add({ rectangle: {
      coordinates: Cesium.Rectangle.fromDegrees(lon - dx / 2, lat - dy / 2, lon + dx / 2, lat + dy / 2), height: 0,
      material: clear ? Cesium.Color.fromCssColorString(slope > 0 ? CELL_UP : CELL_DOWN).withAlpha(0.5) : Cesium.Color.TRANSPARENT,
      outline: !clear, outlineColor: Cesium.Color.WHITE.withAlpha(0.18),
    } });
  }
  cellLayer.show = $("showcells").checked;
}

function drawBox(box) {
  if (state.box) viewer.entities.remove(state.box);
  state.box = null;
  if (!box) return;
  const [s, w, n, e] = box;                  // outline only, so the coast and names inside stay visible
  state.box = viewer.entities.add({ polyline: { positions: lifted([w, s, e, s, e, n, w, n, w, s]), width: 3,
    arcType: Cesium.ArcType.RHUMB, material: Cesium.Color.fromCssColorString(ACCENT) } });
}

function drawChart(t) {
  const up = t.fit.map((f, i) => f + t.band[i]), lo = t.fit.map((f, i) => f - t.band[i]);
  const yTitle = [t.unit, t.baseline].filter(Boolean).join(" ");
  Plotly.react("chart", [
    { x: t.years, y: up, mode: "lines", line: { width: 0 }, hoverinfo: "skip", showlegend: false },
    { x: t.years, y: lo, mode: "lines", line: { width: 0 }, fill: "tonexty", fillcolor: "rgba(229,184,79,0.13)", name: "95% band", hoverinfo: "skip" },
    { x: t.years, y: t.fit, mode: "lines", line: { color: ACCENT, width: 2 }, name: "trend" },
    { x: t.years, y: t.values, mode: "lines+markers", line: { color: "#a9b6c6", width: 1.25 }, marker: { size: 4 }, name: "yearly value",
      hovertemplate: "%{x}: %{y:.3g}<extra></extra>" },
    ...(state.pin && state.pin !== t ? [{ x: state.pin.years, y: state.pin.values, mode: "lines", yaxis: state.pin.unit !== t.unit ? "y2" : "y",
      line: { color: PIN_COLOR, width: 1.5, dash: "dash" }, name: "A (kept)", hovertemplate: "A %{x}: %{y:.3g}<extra></extra>" }] : []),
    ...(state.witness?.for === t ? [{ x: state.witness.years, y: state.witness.values, mode: "lines+markers",
      line: { color: "#6cc79a", width: 1, dash: "dot" }, marker: { size: 3 }, name: "weather station", hovertemplate: "station %{x}: %{y:.3g}<extra></extra>" }] : []),
  ], {
    height: 190,                            // the empty-state CSS collapses #chart, so don't let Plotly measure it
    margin: { l: 56, r: state.pin && state.pin !== t && state.pin.unit !== t.unit ? 56 : 12, t: 8, b: 28 }, paper_bgcolor: "rgba(0,0,0,0)", plot_bgcolor: "rgba(0,0,0,0)",
    font: { color: "#9a9ba3", size: 11, family: "Geist Mono, ui-monospace, monospace" }, showlegend: true,
    legend: { orientation: "h", x: 0, y: 1.15, font: { family: "Geist, system-ui, sans-serif", size: 12, color: "#ececee" } },
    hoverlabel: { bgcolor: "#1b1c20", bordercolor: "#26272c", font: { family: "Geist Mono, monospace", color: "#ececee" } },
    xaxis: { gridcolor: "#1f2024", zeroline: false }, yaxis: { gridcolor: "#1f2024", zeroline: false, title: { text: yTitle, font: { family: "Geist, system-ui, sans-serif", size: 12 } } },
    ...(state.pin && state.pin !== t && state.pin.unit !== t.unit ? { yaxis2: { overlaying: "y", side: "right", showgrid: false, zeroline: false,
      title: { text: `A: ${state.pin.unit}`, font: { color: PIN_COLOR, size: 12 } }, tickfont: { color: PIN_COLOR } } } : {}),
    shapes: [{ type: "line", x0: currentYear(), x1: currentYear(), yref: "paper", y0: 0, y1: 1, line: { color: ACCENT, width: 1, dash: "dot" } }],
  }, { displayModeBar: false, responsive: true });
}

// ---------- compare two results, download the numbers ----------
const PIN_COLOR = "#b48cff";                 // keep in sync with --pin in style.css
const nameOf = (t) => t.name || state.vars[t.var]?.name;

function renderCompare(t) {
  // pinned result A vs current result B: same direction or opposite?
  const a = state.pin, el = $("compare");
  el.hidden = !a || !t || a === t;
  if (el.hidden) return;
  const word = (x) => (x.level === "significant" ? "clear" : x.level === "borderline" ? "maybe" : "no clear trend");
  const row = (x, tag) => `<li><b>${tag}</b> ${esc(nameOf(x))} ${esc(x.region)}: ${sign(x.slope_per_decade)}${fmt(x.slope_per_decade)} ${esc(x.unit)} per decade (${word(x)})</li>`;
  const clearBoth = a.level === "significant" && t.level === "significant";
  const opposite = Math.sign(a.slope_per_decade) !== Math.sign(t.slope_per_decade);
  el.innerHTML = `<span class="badge">Comparing</span>
    <h2>${clearBoth ? (opposite ? "Opposite trends: one rises while the other falls." : "Both change clearly, in the same direction.")
      : "At least one of them has no clear trend, so they can't be called the same or opposite yet."}</h2>
    <ul>${row(a, "A")}${row(t, "B")}</ul>
    <p>A is the dashed purple line on the chart${a.unit !== t.unit ? " (right-hand scale)" : ""}. Press Compare again to stop.</p>`;
}

$("pin").addEventListener("click", () => {
  state.pin = state.pin ? null : Object.assign(state.trend, { var: state.v.id });
  $("pin").classList.toggle("on", !!state.pin);
  $("pin").textContent = state.pin ? "Stop comparing" : "Compare";
  if (state.pin) $("hint").textContent = "Kept as A. Now click another place, or pick another variable, to compare.";
  renderCompare(state.trend);
  drawChart(state.trend);
});

$("csv").addEventListener("click", () => {
  const t = state.trend, w = state.witness?.for === t ? state.witness : null, a = state.pin !== t ? state.pin : null;
  const years = [...new Set([...t.years, ...(w?.years || []), ...(a?.years || [])])].sort();
  const at = (s, y, key = "values") => { const i = s ? s.years.indexOf(y) : -1; return i < 0 ? "" : s[key][i]; };
  const rows = [["year", `${nameOf(t) || "value"} ${t.region} (${t.unit})`, "trend line", w ? `station ${w.station}` : null, a ? `A: ${nameOf(a)} ${a.region} (${a.unit})` : null].filter((x) => x !== null),
    ...years.map((y) => [y, at(t, y), at(t, y, "fit"), ...(w ? [at(w, y)] : []), ...(a ? [at(a, y)] : [])])];
  rows.push([], [`Source: ${t.source}`], ...(w ? [[`Station: ${w.source}`]] : []), [`Made with Earth Trend Detective, ${new Date().toISOString().slice(0, 10)}`]);
  const csv = rows.map((r) => r.map((c) => (/[",\n]/.test(String(c)) ? `"${String(c).replace(/"/g, '""')}"` : c)).join(",")).join("\n");
  const link = Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([csv], { type: "text/csv" })),
    download: `${state.v.id}_${t.years[0]}-${t.years.at(-1)}.csv` });
  link.click();
  URL.revokeObjectURL(link.href);
});

// ---------- case files: ready-made investigations ----------
let CASES = [];
fetch("cases.json").then((r) => r.json()).then((cs) => {
  CASES = cs;
  cs.forEach((c, i) => { $("cases").append(new Option(c.title, i)); BN[c.title] = c.bn; });
  applyLang();
});

function openCase(c) {
  state.scope = null;                        // stop selectVariable re-running the previous place
  $("month").value = c.month || 0;
  if (c.size) $("size").value = c.size;
  $("variable").value = c.var;
  selectVariable();
  $("from").value = c.from;
  $("to").value = c.to;
  buildTimeline();
  if (!c.global) {
    const d = Math.max(c.size, 6);
    viewer.camera.flyTo({ destination: Cesium.Rectangle.fromDegrees(c.lon - d, c.lat - d / 1.5, c.lon + d, c.lat + d / 1.5), duration: 1.2 });
  }
  investigate(c.global ? "global" : "box", c.lat, c.lon);
  $("hint").textContent = c.note;
}

// ---------- English / বাংলা: interface words swap; long result sentences stay English (the coach explains in বাংলা) ----------
const BN = {
  "Case files": "কেস ফাইল", "Pick a case…": "একটি কেস বেছে নিন…", "Variable": "বিষয়", "Years": "বছর", "Month": "মাস", "Box": "এলাকার আকার",
  "to": "থেকে", "All year (annual mean)": "সারা বছর (বার্ষিক গড়)", "Whole Earth": "পুরো পৃথিবী", "Opacity": "স্বচ্ছতা",
  "Click anywhere on the globe to investigate that spot.": "যে জায়গাটি পরীক্ষা করতে চান, গ্লোবে সেখানে ক্লিক করুন।",
  "Click a spot on the globe to investigate it. Drag to move, scroll or +/− to zoom.": "পরীক্ষা করতে গ্লোবে একটি জায়গায় ক্লিক করুন। সরাতে টানুন, জুম করতে স্ক্রল বা +/− চাপুন।",
  "What the numbers show": "সংখ্যাগুলো কী বলছে", "The science behind this": "এর পেছনের বিজ্ঞান", "About this layer": "এই স্তর সম্পর্কে",
  "Why it matters": "কেন এটা গুরুত্বপূর্ণ", "What happened here": "এখানে কী ঘটেছে", "Is it steady?": "পরিবর্তনটা কি স্থির?",
  "Second witness: a weather station": "দ্বিতীয় সাক্ষী: একটি আবহাওয়া কেন্দ্র", "Full check-up of this place": "এই জায়গার পূর্ণ পরীক্ষা",
  "Run the check-up": "পরীক্ষা চালান", "Clear trend": "স্পষ্ট প্রবণতা", "Maybe a trend": "হয়তো প্রবণতা", "No clear trend": "স্পষ্ট প্রবণতা নেই",
  "Comparing": "তুলনা চলছে", "Compare": "তুলনা", "Stop comparing": "তুলনা বন্ধ", "Trend of each grid cell": "প্রতিটি ঘরের প্রবণতা",
  "rising": "বাড়ছে", "falling": "কমছে", "not clear": "স্পষ্ট নয়", "Small change": "ছোট পরিবর্তন", "Big change": "বড় পরিবর্তন",
  "Real": "সত্যি", "Not sure": "নিশ্চিত নয়", "small but real": "ছোট কিন্তু সত্যি", "big and real": "বড় এবং সত্যি",
  "lost in the noise": "স্বাভাবিক ওঠানামায় হারিয়ে গেছে", "big but uncertain": "বড় কিন্তু অনিশ্চিত",
  "Ask the coach": "কোচকে জিজ্ঞেস করুন", "Ask": "জিজ্ঞেস করুন",
};
for (const [i, m] of MONTHS.entries()) BN[m] = ["জানুয়ারি", "ফেব্রুয়ারি", "মার্চ", "এপ্রিল", "মে", "জুন", "জুলাই", "আগস্ট", "সেপ্টেম্বর", "অক্টোবর", "নভেম্বর", "ডিসেম্বর"][i];
const EN = new WeakMap();                    // text node -> its English original
let lang = "en";
try { lang = localStorage.getItem("lang") || "en"; } catch { /* private window: stay English */ }

function applyLang(root = document.body) {
  const walk = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let n; (n = walk.nextNode());) {
    const en = EN.get(n) ?? n.nodeValue.trim();
    if (!(en in BN)) continue;
    EN.set(n, en);
    const want = lang === "bn" ? BN[en] : en;
    if (n.nodeValue.trim() !== want) n.nodeValue = n.nodeValue.replace(n.nodeValue.trim(), want);
  }
  document.documentElement.lang = lang;
  const label = lang === "bn" ? "English" : "বাংলা";  // only write on change: a write here would re-fire the observer forever
  if ($("lang").textContent !== label) { $("lang").textContent = label; $("lang").lang = lang === "bn" ? "en" : "bn"; }
}
// anything drawn later (verdicts, panels, case list) gets translated as it appears
new MutationObserver(() => lang === "bn" && applyLang()).observe(document.body, { childList: true, subtree: true });
$("lang").addEventListener("click", () => {
  lang = lang === "bn" ? "en" : "bn";
  try { localStorage.setItem("lang", lang); } catch { /* not saved, still switches */ }
  applyLang();
});

// ---------- controls ----------
for (const b of document.querySelectorAll("#coach .quick button")) b.addEventListener("click", () => askCoach(b.dataset.q, b.dataset.lang || lang));
$("askform").addEventListener("submit", (e) => { e.preventDefault(); if ($("question").value.trim()) askCoach($("question").value.trim()); });
$("cases").addEventListener("change", () => { if ($("cases").value) openCase(CASES[$("cases").value]); });
$("variable").addEventListener("change", selectVariable);
$("month").addEventListener("change", () => { buildTimeline(); if (state.scope) investigate(state.scope, state.lat, state.lon); });
for (const id of ["from", "to"]) $(id).addEventListener("change", () => { buildTimeline(); if (state.scope) investigate(state.scope, state.lat, state.lon); });
$("size").addEventListener("change", () => { if (state.scope === "box") investigate("box", state.lat, state.lon); });
$("global").addEventListener("click", () => investigate("global", state.lat || 70, 0));
$("showcells").addEventListener("change", () => { cellLayer.show = $("showcells").checked; });
$("opacity").addEventListener("input",() => { if (state.dataLayer) state.dataLayer.alpha = Number($("opacity").value); });
$("speed").addEventListener("change", () => { viewer.clock.multiplier = SEC_PER_YEAR * Number($("speed").value); });
$("play").addEventListener("click", () => setPlaying(!viewer.clock.shouldAnimate));
$("zin").addEventListener("click", () => zoomBy(0.6));
$("zout").addEventListener("click", () => zoomBy(1.6));
$("home").addEventListener("click", () => goHome());
$("mode").addEventListener("click", () => setFlat(!is2D()));
$("scrub").addEventListener("input", () => { setPlaying(false); seekYear(Number($("scrub").value)); });
document.addEventListener("keydown", (e) => {
  if (["INPUT", "SELECT", "TEXTAREA"].includes(e.target.tagName)) return;
  if (e.code === "Space") { e.preventDefault(); setPlaying(!viewer.clock.shouldAnimate); }
  if (e.code === "ArrowRight") { setPlaying(false); seekYear(currentYear() + 1); }
  if (e.code === "ArrowLeft") { setPlaying(false); seekYear(currentYear() - 1); }
  if (e.code === "Equal" || e.code === "NumpadAdd") zoomBy(0.6);
  if (e.code === "Minus" || e.code === "NumpadSubtract") zoomBy(1.6);
});
