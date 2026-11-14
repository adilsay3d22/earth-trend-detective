"""Earth Trend Detective backend: serves the catalog, fetches NASA series (disk-cached) and runs trend tests.
Tokens from .env stay on this server and are never sent to the browser.
Run: .venv/Scripts/python.exe -m uvicorn app.server:app --port 8000"""
import hashlib
import json
import math
import pathlib
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date

import numpy as np
import pymannkendall as mk
import requests
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles

from app import trends

ROOT = pathlib.Path(__file__).resolve().parent.parent
CATALOG = json.loads((ROOT / "research" / "catalog.json").read_text(encoding="utf-8"))
VARS = {v["id"]: v for v in CATALOG["variables"]}
CITIES = json.loads((ROOT / "app" / "static" / "places.json").read_text(encoding="utf-8"))["cities"]  # biggest first
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
CACHE = ROOT / "cache"
CACHE.mkdir(exist_ok=True)
_env = ROOT / ".env"
ENV = dict(l.split("=", 1) for l in _env.read_text().splitlines() if "=" in l) if _env.exists() else {}
EDL = {"Authorization": f"Bearer {ENV.get('EARTHDATA_TOKEN', '').strip()}"}
CMR = "https://cmr.earthdata.nasa.gov/search/granules.umm_json"
DATA = ROOT / "app" / "data"
BD_MODIS = json.loads((DATA / "bd_modis.json").read_text(encoding="utf-8"))["points"]
ORNL = "https://modis.ornl.gov/rst/api/v1"

app = FastAPI(title="Earth Trend Detective")
PRETTY_UNITS = {"C": "°C", "kg m-2": "kg/m²", "MJ/m^2/day": "MJ/m²/day", "m/s": "m/s", "1": "", "W m-2 x 40": ""}


def cached(key, fetch):
    # ponytail: cache never expires; delete cache/ to refresh before the final demo build
    p = CACHE / (hashlib.sha1(key.encode()).hexdigest()[:16] + ".json")
    if p.exists():
        return json.loads(p.read_text())
    data = fetch()
    p.write_text(json.dumps(data))
    return data


def route(var, name):
    return next((a for a in var["access"] if a["route"] == name), None)


def dec_to_month(t):
    y = int(t)
    return f"{y}-{min(12, int((t - y) * 12) + 1):02d}"


def monthly_mean(rows):  # [(t_decimal, value)] -> [["YYYY-MM", mean]]
    by = {}
    for t, v in rows:
        by.setdefault(dec_to_month(t), []).append(v)
    return [[k, sum(v) / len(v)] for k, v in sorted(by.items())]


def place_name(box):
    """Name a big city in the box, closest to its centre, so people read 'near Dhaka, Bangladesh' instead of coordinates."""
    s, w, n, e = box
    lat, lon = (s + n) / 2, (w + e) / 2
    inside = [c for c in CITIES if s <= c[2] <= n and w <= c[1] <= e]
    if inside:  # rank buckets: 0-2 major cities, 3-5 regional, 6+ small; nearest wins within the best bucket
        c = min(inside, key=lambda c: (c[3] // 3, (c[1] - lon) ** 2 + (c[2] - lat) ** 2))
        return f"near {c[0]}" + (f", {c[4]}" if c[4] != c[0] else "")
    return f"around {abs(lat):.0f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.0f}°{'E' if lon >= 0 else 'W'}"


def box_around(lat, lon, size):
    """POWER regional boxes must span 2-10 degrees in both directions; keep inside the globe."""
    size = min(10.0, max(2.0, size))
    s = min(90 - size, max(-90, round(lat - size / 2, 1)))
    w = min(180 - size, max(-180, round(lon - size / 2, 1)))
    return s, w, round(s + size, 1), round(w + size, 1)


# ---- sources: each returns {"monthly": [["YYYY-MM", v]], "unit", "region", "source", "link"} ----

def power(param, box):
    s, w, n, e = box
    q = {"parameters": param, "community": "AG", "start": 1981, "end": 2025, "format": "JSON",
         "latitude-min": s, "latitude-max": n, "longitude-min": w, "longitude-max": e}
    r = requests.get("https://power.larc.nasa.gov/api/temporal/monthly/regional", params=q, timeout=300)
    r.raise_for_status()
    d = r.json()
    acc, cells = {}, []
    for f in d["features"]:
        lon, lat = f["geometry"]["coordinates"][:2]
        wt = math.cos(math.radians(lat))
        good = {k: v for k, v in f["properties"]["parameter"][param].items() if not k.endswith("13") and v is not None and v > -998}
        cells.append([lat, lon, [[f"{k[:4]}-{k[4:]}", v] for k, v in sorted(good.items())]])
        for k, v in good.items():
            a = acc.setdefault(k, [0.0, 0.0])
            a[0] += wt * v
            a[1] += wt
    unit = d["parameters"][param]["units"]
    return {"monthly": [[f"{k[:4]}-{k[4:]}", a[0] / a[1]] for k, a in sorted(acc.items())], "cells": cells, "unit": unit, "box": list(box),
            "region": f"in the box {abs(s)}°{'N' if s >= 0 else 'S'}–{abs(n)}°{'N' if n >= 0 else 'S'}, "
                      f"{abs(w)}°{'E' if w >= 0 else 'W'}–{abs(e)}°{'E' if e >= 0 else 'W'}",
            "source": f"NASA POWER {param} (MERRA-2 / CERES), monthly 1981–2025",
            "link": "https://power.larc.nasa.gov/"}


def power_daily(a, box):
    """Days per month above a threshold, from NASA POWER daily values at the centre of the box."""
    s, w, n, e = box
    lat, lon = round((s + n) / 2, 2), round((w + e) / 2, 2)
    r = requests.get("https://power.larc.nasa.gov/api/temporal/daily/point", timeout=300, params={
        "parameters": a["id"], "community": "AG", "latitude": lat, "longitude": lon, "start": "19810101", "end": "20251231", "format": "JSON"})
    r.raise_for_status()
    counts = {}
    for day, v in r.json()["properties"]["parameter"][a["id"]].items():
        if v > -998:
            k = f"{day[:4]}-{day[4:6]}"
            counts[k] = counts.get(k, 0) + (v >= a["above"])
    where = f"at {abs(lat):.1f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.1f}°{'E' if lon >= 0 else 'W'} ({place_name(box)})"
    return {"monthly": sorted(counts.items()), "total": True, "min_months": 12, "unit": "days", "box": list(box), "where": where,
            "region": where, "area_note": "Daily values at the centre of the box (one 0.5° grid cell), counted day by day.",
            "source": a["source"], "link": "https://power.larc.nasa.gov/"}


def gistemp():
    lines = requests.get("https://data.giss.nasa.gov/gistemp/tabledata_v4/GLB.Ts+dSST.csv", timeout=60).text.splitlines()
    out = []
    for l in lines[2:]:
        p = l.split(",")
        for m in range(12):
            if p[m + 1].strip() not in ("***", ""):
                out.append([f"{p[0]}-{m + 1:02d}", float(p[m + 1])])
    return {"monthly": out, "unit": "°C", "baseline": "vs the 1951–1980 average", "region": "across the whole planet",
            "source": "NASA GISS Surface Temperature Analysis (GISTEMP v4)", "link": "https://data.giss.nasa.gov/gistemp/"}


def nsidc(north):
    h = "north" if north else "south"

    def one(m):
        url = f"https://noaadata.apps.nsidc.org/NOAA/G02135/{h}/monthly/data/{'N' if north else 'S'}_{m:02d}_extent_v4.0.csv"
        rows = [l.split(",") for l in requests.get(url, timeout=60).text.strip().splitlines()[1:]]
        return [[f"{int(r[0])}-{int(r[1]):02d}", float(r[4])] for r in rows if float(r[4]) > 0]

    with ThreadPoolExecutor(12) as ex:
        out = sorted(x for part in ex.map(one, range(1, 13)) for x in part)
    return {"monthly": out, "unit": "million km²", "region": "in the Arctic" if north else "around Antarctica",
            "source": "NSIDC Sea Ice Index v4 (G02135), sea-ice extent", "link": "https://nsidc.org/data/g02135"}


def podaac_rows(short_name):
    g = requests.get(CMR, params={"short_name": short_name, "sort_key": "-start_date", "page_size": 1}, timeout=60)
    umm = g.json()["items"][0]["umm"]
    url = next(u["URL"] for u in umm["RelatedUrls"] if u.get("Type") == "GET DATA" and u["URL"].startswith("https"))
    r = requests.get(url, headers=EDL, timeout=120)
    r.raise_for_status()
    return [[float(x) for x in l.split()] for l in r.text.splitlines() if l.strip() and not l.startswith("HDR")]


def sea_level():
    rows = podaac_rows("NASA_SSH_GMSL_INDICATOR")  # year.decimal, GMSL cm, smoothed cm
    return {"monthly": monthly_mean([(r[0], r[1] * 10) for r in rows]), "unit": "mm", "baseline": "vs the 1993 average", "region": "across the world's oceans",
            "source": "NASA-SSH Global Mean Sea Level indicator (TOPEX/Jason/Sentinel-6), doi:10.5067/NSIND-GMSV1",
            "link": "https://podaac.jpl.nasa.gov/dataset/NASA_SSH_GMSL_INDICATOR"}


def ice_mass(north):
    name = "GREENLAND" if north else "ANTARCTICA"
    rows = podaac_rows(f"{name}_MASS_TELLUS_MASCON_CRI_TIME_SERIES_RL06.3_V4")  # year.decimal, Gt, sigma
    # ponytail: GRACE misses months most years (and Jul 2017-May 2018), so a year counts with >=6 months
    return {"monthly": monthly_mean([(r[0], r[1]) for r in rows]), "unit": "Gt", "baseline": "vs April 2002",
            "name": "Ice sheet mass", "min_months": 6, "region": "in Greenland" if north else "in Antarctica",
            "source": "GRACE + GRACE-FO JPL mascons RL06.3 v4, doi:10.5067/TEMSC-3JC634",
            "link": "https://podaac.jpl.nasa.gov/dataset/TELLUS_GRAC-GRFO_MASCON_CRI_GRID_RL06.3_V4"}


def ornl_get(url):
    for i in range(3):
        try:
            r = requests.get(url, headers={"Accept": "application/json"}, timeout=180)
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            if i == 2:
                raise


def modis(a, box):
    """Yearly MODIS values at a point. Bangladesh district centres come from TerraBangla's cache; anywhere else is
    fetched live from the ORNL DAAC subset API (3x3 pixels at the box centre, 10 dates per request)."""
    s, w, n, e = box
    lat, lon = round((s + n) / 2, 3), round((w + e) / 2, 3)
    inside = [p for p in BD_MODIS if s <= p["lat"] <= n and w <= p["lon"] <= e]
    if inside:
        p = min(inside, key=lambda p: (p["lat"] - lat) ** 2 + (p["lon"] - lon) ** 2)
        lat, lon = p["lat"], p["lon"]
        annual = [[int(y), v] for y, v in sorted(p[a["key"]].items())]
        where, src = f"at the centre of {p['name']} district, Bangladesh", a["source"] + "; downloaded 2026-09-26 by team TerraBangla"
        note = "One MODIS pixel at the district centre, not the whole box. Yearly mean of every cloud-free image."
    else:
        dates = [d["modis_date"] for d in ornl_get(f"{ORNL}/{a['id']}/dates?latitude={lat}&longitude={lon}")["dates"]]

        def chunk(ds):
            j = ornl_get(f"{ORNL}/{a['id']}/subset?latitude={lat}&longitude={lon}&band={a['band']}"
                         f"&startDate={ds[0]}&endDate={ds[-1]}&kmAboveBelow=1&kmLeftRight=1")
            return [(int(x["modis_date"][1:5]), v * a["scale"] + a["offset"]) for x in j["subset"] for v in x["data"] if v != a["fill"]]

        with ThreadPoolExecutor(8) as ex:
            rows = [r for part in ex.map(chunk, [dates[i:i + 10] for i in range(0, len(dates), 10)]) for r in part]
        per_year = {}
        for y, v in rows:
            per_year.setdefault(y, []).append(v)
        full = {y for y in per_year if sum(d[1:5] == str(y) for d in dates) >= 20}  # 16-day: 23 dates, 8-day: 46
        annual = [[y, float(np.mean(per_year[y]))] for y in sorted(full) if len(per_year[y]) >= 8]
        note = "MODIS pixels in a 3 km square at the centre of the box, not the whole box. Yearly mean of every cloud-free image."
        where, src = f"at {abs(lat):.2f}°{'N' if lat >= 0 else 'S'}, {abs(lon):.2f}°{'E' if lon >= 0 else 'W'} ({place_name(box)})", a["source"]
    d = 0.05
    return {"annual": annual, "unit": a["unit"], "box": [lat - d, lon - d, lat + d, lon + d], "events_box": list(box),
            "where": where, "region": where, "area_note": note, "source": src, "link": "https://modis.ornl.gov/data/modis_webservice.html"}


_chl = {}


def chlorophyll(box):
    """Box log-mean of the precomputed yearly 0.5 deg chlorophyll grid (app/build_chl.py)."""
    if not _chl:
        z = np.load(DATA / "chl_yearly.npz")
        _chl.update(years=z["years"].tolist(), g=z["log10_chl"].astype("float32"))
    s, w, n, e = box
    rows = slice(int((90 - n) * 2), int(math.ceil((90 - s) * 2)))
    cols = slice(int((w + 180) * 2), int(math.ceil((e + 180) * 2)))
    cells = _chl["g"][:, rows, cols]
    annual = []
    for y, c in zip(_chl["years"], cells):
        if np.isfinite(c).sum() >= 4:
            annual.append([y, float(10 ** np.nanmean(c))])
    if not annual:
        raise HTTPException(400, "No ocean in this box: chlorophyll is only measured over the sea. Click on the ocean or a coast.")
    return {"annual": annual, "unit": "mg/m³", "box": list(box), "where": f"in the sea {place_name(box)}", "region": f"in the box {box}",
            "area_note": f"Log-average of the 0.5° ocean cells in the box; land and cloud-only cells are skipped.", "source": "MODIS Aqua yearly chlorophyll-a 9 km (NASA OB.DAAC R2022.0)",
            "link": "https://doi.org/10.5067/AQUA/MODIS/L3M/CHL/2022"}


def event_spot(ev, box):
    """(lon, lat) of the first part of an EONET event inside box (s, w, n, e), else None. Storms are tracks, so any
    point counts. GDACS flood polygons store [lat, lon] (others [lon, lat]), which also fools EONET's own bbox filter."""
    s, w, n, e = box
    gdacs = any(x["id"] == "GDACS" for x in ev["sources"])
    for g in ev["geometry"]:
        if g["type"] == "Point":
            lon, lat = g["coordinates"][:2]
        else:
            ring = g["coordinates"][0]
            a, b = sum(p[0] for p in ring) / len(ring), sum(p[1] for p in ring) / len(ring)
            lon, lat = (b, a) if gdacs else (a, b)
        if s <= lat <= n and w <= lon <= e:
            return lon, lat, g["date"][:10]
    return None


def eonet(box):
    s, w, n, e = box
    r = requests.get("https://eonet.gsfc.nasa.gov/api/v3/events", timeout=120,
                     params={"bbox": f"{w},{n},{e},{s}", "start": "1979-01-01", "end": "2030-12-31", "status": "all"})
    r.raise_for_status()
    out = []
    for ev in r.json()["events"]:
        spot = event_spot(ev, box)
        if spot and "prescribed" not in ev["title"].lower():  # planned burns are not natural events
            out.append({"title": " ".join(re.sub(r"\s\d{6,}$", "", ev["title"]).split()),  # drop GDACS id numbers
                        "cat": ev["categories"][0]["title"], "cat_id": ev["categories"][0]["id"],
                        "lon": round(spot[0], 2), "lat": round(spot[1], 2), "date": spot[2],
                        "url": ev["sources"][0]["url"] if ev["sources"] else None})
    return sorted(out, key=lambda x: x["date"])


# areas for event lookups when a series has no box; lat >= 0 picks the hemisphere
EVENT_AREAS = {("sea_ice", True): [60, -180, 90, 180], ("sea_ice", False): [-90, -180, -55, 180],
               ("ice_sheet_mass", True): [59, -75, 84, -10], ("ice_sheet_mass", False): [-90, -180, -60, 180]}

GLOBAL = {  # variables with a whole-planet (or hemisphere) series; lat picks the hemisphere
    "global_temp": lambda lat: ("gistemp", gistemp),
    "sea_ice": lambda lat: (f"nsidc{lat >= 0}", lambda: nsidc(lat >= 0)),
    "sea_level": lambda lat: ("gmsl", sea_level),
    "ice_sheet_mass": lambda lat: (f"grace{lat >= 0}", lambda: ice_mass(lat >= 0)),
}


def series(var_id, scope, lat, lon, size):
    if var_id not in VARS:
        raise HTTPException(404, f"Unknown variable {var_id}")
    var = VARS[var_id]
    p = route(var, "power")
    box = box_around(lat, lon, size)
    if scope == "box" and p:
        return cached(f"power2:{p['id']}:{box}", lambda: power(p["id"], box))  # power2: cached files also keep each grid cell
    if scope == "box" and (d := route(var, "power_daily")):
        return cached(f"powerd:{d['id']}:{d['above']}:{box}", lambda: power_daily(d, box))
    if scope == "box" and (m := route(var, "modis")):
        return cached(f"modis:{m['id']}:{m['band']}:{box}", lambda: modis(m, box))
    if scope == "box" and route(var, "obdaac"):
        return chlorophyll(box)
    if var_id in GLOBAL:
        key, fetch = GLOBAL[var_id](lat)
        return cached(key, fetch)
    if p:
        raise HTTPException(400, "Whole-Earth numbers for this variable need the MERRA-2 grid (coming next). Click a spot on the globe to use a box.")
    raise HTTPException(400, f"Numbers for {var['name']} come from {', '.join(a['route'] for a in var['access'])} - not wired up yet. The map still works.")


# ---- API ----

@app.get("/api/variables")
def variables():
    return [{k: v.get(k) for k in ("id", "name", "domain", "unit", "plain", "good_for", "look", "notes", "story")}
            | {"box": any(route(v, r) for r in ("power", "power_daily", "modis", "obdaac")), "global": v["id"] in GLOBAL} for v in CATALOG["variables"]]


def cell_trends(cells, month, start, end, min_months):
    """Trend of every grid cell in the box, so opposite trends inside one region show up on the map."""
    out = []
    for lat, lon, monthly in cells:
        ys, vs = trends.yearly(monthly, month, min_months)
        vs = [v for y, v in zip(ys, vs) if start <= y <= end]
        if len(vs) >= 8 and max(vs) > min(vs):
            m = mk.original_test(vs)
            out.append([lat, lon, round(float(m.slope) * 10, 6), round(float(m.p), 4)])
    lats, lons = sorted({c[0] for c in cells}), sorted({c[1] for c in cells})
    step = [lats[1] - lats[0] if len(lats) > 1 else 0.5, lons[1] - lons[0] if len(lons) > 1 else 0.625]
    up = sum(1 for c in out if c[3] < 0.05 and c[2] > 0)
    down = sum(1 for c in out if c[3] < 0.05 and c[2] < 0)
    return {"cells": out, "cell_step": step, "cells_up": up, "cells_down": down}


@app.get("/api/trend")
def trend(var: str, scope: str = "box", lat: float = 0, lon: float = 0, size: float = 4,
          month: int = 0, start: int = 1900, end: int = 2100):
    try:
        s = series(var, scope, lat, lon, size)
    except requests.RequestException as e:
        raise HTTPException(502, f"NASA service did not answer: {e.__class__.__name__}. Try again in a moment.")
    s = s | {"unit": PRETTY_UNITS.get(s["unit"], s["unit"])}
    if "annual" in s:  # sources stored as yearly means only
        years, values = [y for y, _ in s["annual"]], [v for _, v in s["annual"]]
    else:
        years, values = trends.yearly(s["monthly"], month, s.get("min_months", 10))
        if s.get("total") and not month:  # counts: the year's total, not the monthly average
            values = [v * 12 for v in values]
    keep = [i for i, y in enumerate(years) if start <= y <= end]
    years, values = [years[i] for i in keep], [values[i] for i in keep]
    name = s.get("name") or (VARS[var].get("story") or {}).get("name") or VARS[var]["name"]
    if month and "annual" not in s:  # "July air temperature", but keep "UV index" capitalised
        name = f"{MONTHS[month - 1]} {name[0].lower() + name[1:] if name[1:2].islower() else name}"
    region = s.get("where") or (place_name(s["box"]) if s.get("box") else s["region"])
    result = trends.analyse(years, values, name, s["unit"], region, anomaly=bool(s.get("baseline")))
    if s.get("cells") and "error" not in result:
        result |= cell_trends(s["cells"], month, start, end, s.get("min_months", 10))
        up, down, k = result["cells_up"], result["cells_down"], len(result["cells"])
        result["facts"].insert(1, (f"Opposite trends inside the same box: {up} grid cells rising clearly and {down} falling clearly "
                                   f"(of {k}). One average hides this, so look at the coloured cells on the map." if up and down else
                                   f"Inside the box, {up + down} of {k} grid cells change clearly on their own, all in the same direction."
                                   if up or down else f"None of the {k} grid cells in the box changes clearly on its own."))
    if month and "annual" in s and "warnings" in result:
        result["warnings"].append("This dataset is stored as yearly averages, so the month choice does not change the numbers.")
    return {"years": years, "values": values, "unit": s["unit"], "baseline": s.get("baseline"), "box": s.get("box"),
            "region": region, "area": s["region"], "source": s["source"],
            "events_box": s.get("events_box") or s.get("box") or EVENT_AREAS.get((var, lat >= 0)), "area_note": s.get("area_note"),
            "link": s["link"], "months": [s["monthly"][0][0], s["monthly"][-1][0]] if s.get("monthly") else None} | result


WITNESS = {"air_temp": "TAVG", "air_temp_max": "TMAX", "air_temp_min": "TMIN", "precip": "PRCP"}  # NOAA GSOM data types
NCEI = "https://www.ncei.noaa.gov/access/services"


def stations_near(dtype, box, start, end):
    """NOAA GHCN stations with this data type in the box, best record first (years covered x completeness)."""
    s, w, n, e = box
    r = requests.get(f"{NCEI}/search/v1/data", timeout=90, params={
        "dataset": "global-summary-of-the-month", "bbox": f"{n},{w},{s},{e}", "dataTypes": dtype,
        "startDate": f"{start}-01-01", "endDate": f"{end}-12-31", "limit": 100})
    r.raise_for_status()
    out = []
    for res in r.json()["results"]:
        st = res["stations"][0]
        dt = next((x for x in st["dataTypes"] if x["id"] == dtype), None)
        if dt:
            y0, y1 = max(start, int(dt["startDate"][:4])), min(end, int(dt["endDate"][:4]))
            lon, lat = res["boundingPoints"][0]["coordinates"]
            out.append({"id": st["id"], "name": st["name"], "lat": lat, "lon": lon, "score": max(0, y1 - y0) * dt["coverage"]})
    return sorted(out, key=lambda x: -x["score"])


def station_monthly(sid, dtype):
    r = requests.get(f"{NCEI}/data/v1", timeout=90, params={"dataset": "global-summary-of-the-month", "stations": sid,
                     "dataTypes": dtype, "startDate": "1900-01-01", "endDate": "2030-12-31", "format": "json", "units": "metric"})
    r.raise_for_status()
    out = []
    for row in r.json():
        if row.get(dtype) not in (None, ""):
            y, m = int(row["DATE"][:4]), int(row["DATE"][5:7])
            v = float(row[dtype])
            if dtype == "PRCP":  # monthly total -> mm/day, like the NASA series
                v /= (date(y + m // 12, m % 12 + 1, 1) - date(y, m, 1)).days
            out.append([row["DATE"][:7], v])
    return out


@app.get("/api/witness")
def witness(var: str, lat: float, lon: float, size: float = 4, month: int = 0, start: int = 1900, end: int = 2100):
    """Second witness: the nearest long-running NOAA weather station inside the box, tested the same way."""
    dtype = WITNESS.get(var)
    if not dtype:
        return {"none": "No ground-station record for this variable."}
    box = box_around(lat, lon, size)
    try:
        cands = cached(f"ncei:{dtype}:{box}", lambda: stations_near(dtype, box, 1980, 2025))[:8]

        def usable(st):  # NOAA's coverage score counts a station's whole history, so test the recent years ourselves
            monthly = cached(f"gsom:{st['id']}:{dtype}", lambda: station_monthly(st["id"], dtype))
            # gappy station: average monthly anomalies (needs 6 months a year, no seasonal bias), then add the mean back
            clim = {}
            for ym, v in monthly:
                clim.setdefault(ym[5:], []).append(v)
            clim = {m: float(np.mean(v)) for m, v in clim.items()}
            base = float(np.mean(list(clim.values()))) if clim else 0
            years, values = trends.yearly([[ym, v - clim[ym[5:]] + base] for ym, v in monthly], month, 6)
            keep = [i for i, y in enumerate(years) if start <= y <= end]
            return st, [years[i] for i in keep], [values[i] for i in keep]

        with ThreadPoolExecutor(8) as ex:
            # most usable years wins, but among stations with 15+ years the nearest one does
            dist = lambda st: (st["lat"] - lat) ** 2 + ((st["lon"] - lon) * math.cos(math.radians(lat))) ** 2
            st, years, values = max(ex.map(usable, cands), key=lambda r: (min(len(r[1]), 15), -dist(r[0])), default=(None, [], []))
        if len(years) < 10:
            return {"none": "No weather station in this box has at least 10 usable years in this range."}
    except requests.RequestException as e:
        return {"none": f"NOAA's station service did not answer ({e.__class__.__name__})."}
    name = st["name"].title().replace(", Bg", ", Bangladesh").replace(", In", ", India")
    res = trends.analyse(years, values, "The station", "", f"at {name}")
    km = 111 * math.hypot(st["lat"] - lat, (st["lon"] - lon) * math.cos(math.radians(lat)))
    return {"station": name, "id": st["id"], "lat": st["lat"], "lon": st["lon"], "km": round(km), "years": years, "values": values,
            "source": f"NOAA NCEI Global Summary of the Month (GHCN), station {st['id']}",
            "link": f"https://www.ncei.noaa.gov/access/search/data-search/global-summary-of-the-month?stations={st['id']}"} | \
        {k: res.get(k) for k in ("level", "slope_per_decade", "ci_per_decade", "p_hamed_rao", "error")}


CHECKUP = ["air_temp", "humid_heat_days", "precip", "soil_moisture_root", "evapotranspiration", "sunshine", "ndvi", "land_temp"]


@app.get("/api/checkup")
def checkup(lat: float, lon: float, size: float = 4, start: int = 1900, end: int = 2100):
    """Every key variable for one place at once, plus a rule-based label (idea and rules from TerraBangla's biome.ts).
    Same inputs always give the same label; no AI involved."""
    def one(v):
        if v in ("ndvi", "land_temp") and not any(abs(p["lat"] - lat) <= size / 2 and abs(p["lon"] - lon) <= size / 2 for p in BD_MODIS):
            return None  # live MODIS is slow; only use it where it is cached
        try:
            t = trend(var=v, lat=lat, lon=lon, size=size, start=start, end=end)
        except (HTTPException, requests.RequestException):
            return None
        if "error" in t:
            return None
        return {"var": v, "name": VARS[v]["name"], "unit": t["unit"], "per_decade": t["slope_per_decade"], "level": t["level"],
                "years": [t["years"][0], t["years"][-1]]}

    with ThreadPoolExecutor(8) as ex:
        rows = [r for r in ex.map(one, CHECKUP) if r]
    clear = {r["var"]: (1 if r["per_decade"] > 0 else -1) for r in rows if r["level"] == "significant"}
    warm, sticky = clear.get("air_temp") == 1, clear.get("humid_heat_days") == 1
    wetter = clear.get("precip", 0) + clear.get("soil_moisture_root", 0)
    green = clear.get("ndvi", 0)
    parts = (["warming"] if warm else ["cooling"] if clear.get("air_temp") == -1 else []) + \
            (["having more humid-heat days"] if sticky else []) + \
            (["getting wetter"] if wetter > 0 else ["drying out"] if wetter < 0 else []) + \
            (["getting greener"] if green > 0 else ["losing green"] if green < 0 else [])
    label = ("This place is " + ", ".join(parts[:-1]) + (" and " if len(parts) > 1 else "") + parts[-1] + ".") if parts else \
        "No clear change in temperature, water or greenness here."
    why = []
    if warm and wetter < 0:
        why.append("Warming plus drying is the combination that raises drought and wildfire risk.")
    if sticky and not warm:
        why.append("The air is not getting hotter on average here, but humid heat is getting more common, and that is the dangerous kind.")
    elif (warm or sticky) and wetter > 0:
        why.append("Warm and wet together means more humid heat, and heavier downpours when it rains.")
    if green < 0 and warm:
        why.append("Losing green while warming can feed itself: bare ground heats up more than plants do.")
    return {"rows": rows, "label": label, "why": why, "region": place_name(box_around(lat, lon, size))}


COACH_SYSTEM = """You are the Trend Detective coach: you help high-school and college students understand one NASA trend result.
Rules:
- Every number you mention must appear in the EVIDENCE JSON. Never calculate, round differently, or invent a value.
- Say clearly what was measured (evidence) and, separately, what might explain it (possible reasons). Never claim a trend proves a cause.
- If the student's idea conflicts with the evidence, say so kindly and show which number disagrees.
- Mention a warning from the evidence when one applies (short record, station disagrees, direction changed).
- Plain words a 15-year-old understands. At most 160 words. No headings, no tables.
- Answer in the language named in LANGUAGE (English or Bangla). In Bangla, keep numbers and units as written in the evidence."""


@app.post("/api/coach")
def coach(q: dict):
    """AI coach (Claude), grounded only in numbers this server computed. Disclosed in the UI and the submission."""
    key = ENV.get("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise HTTPException(503, "The AI coach is switched off: add ANTHROPIC_API_KEY to the .env file on the server.")
    question = str(q.get("question", ""))[:500].strip() or "Explain this result simply."
    p = {k: q[k] for k in ("var", "lat", "lon", "size", "month", "start", "end") if k in q}
    t = trend(scope=q.get("scope", "box"), **p)  # recompute: never trust numbers sent by the browser
    if "error" in t:
        raise HTTPException(400, t["error"])
    v = VARS[p["var"]]
    ev = {"variable": v["name"], "definition": v.get("plain"), "why_it_matters": (v.get("story") or {}).get("why"),
          "where": t["region"], "years": [t["years"][0], t["years"][-1]], "unit": t["unit"]} | \
         {k: t.get(k) for k in ("verdict", "meaning", "facts", "warnings", "details", "stability", "quadrant", "periods",
                                "cells_up", "cells_down", "source")}
    if p["var"] in WITNESS and q.get("scope", "box") == "box":
        try:
            w = witness(**p)
            ev["weather_station"] = {k: w.get(k) for k in ("station", "km", "slope_per_decade", "level", "none")}
        except Exception:  # the station check is a bonus; the coach still works without it
            pass
    import anthropic  # only needed when the coach is used
    try:
        r = anthropic.Anthropic(api_key=key).beta.messages.create(
            model="claude-opus-5-5", max_tokens=2000, output_config={"effort": "low"},
            betas=["server-side-fallback-2026-07-01"], fallbacks="default",
            system=COACH_SYSTEM,
            messages=[{"role": "user", "content": f"LANGUAGE: {'Bangla' if q.get('lang') == 'bn' else 'English'}\n"
                                                  f"EVIDENCE:\n{json.dumps(ev, ensure_ascii=False, default=float)}\n\nSTUDENT: {question}"}])
    except anthropic.APIConnectionError:
        raise HTTPException(502, "Could not reach the AI service. Try again in a moment.")
    except anthropic.RateLimitError:
        raise HTTPException(429, "The AI coach is busy. Try again in a minute.")
    except anthropic.APIStatusError as e:
        raise HTTPException(502, f"The AI service returned an error ({e.status_code}).")
    if r.stop_reason == "refusal":
        return {"answer": "The coach can't answer that one. Try asking about the trend, the numbers or what might explain them."}
    return {"answer": "".join(b.text for b in r.content if b.type == "text").strip()}


@app.get("/api/events")
def events(s: float, w: float, n: float, e: float, start: int = 1979, end: int = 2030):
    """NASA EONET natural events inside the area, between the start and end years."""
    if not (-90 <= s < n <= 90 and -180 <= w < e <= 180):
        raise HTTPException(400, "Area must be south < north within ±90 and west < east within ±180.")
    try:
        evs = cached(f"eonet:{s},{w},{n},{e}", lambda: eonet((s, w, n, e)))
    except requests.RequestException as x:
        raise HTTPException(502, f"NASA EONET did not answer: {x.__class__.__name__}. Try again in a moment.")
    return [v for v in evs if start <= int(v["date"][:4]) <= end]


app.mount("/", StaticFiles(directory=ROOT / "app" / "static", html=True), name="static")
