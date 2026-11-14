# Earth Trend Detective

**NASA Space Apps Challenge 2026: "Earth System Trend Detective"**

Click anywhere on a 3D globe, pick something to investigate (air temperature, rain, soil water, sea ice, ocean chlorophyll, vegetation greenness and more) and get an honest answer to one question: **is it really changing here, or is it just noise?**

Every result is a real statistical trend test on NASA data, explained in words a 15-year-old understands, in **English or বাংলা**.

---

## What it does

| Feature | What you see |
|---|---|
| **Trend verdict** | "Clear trend", "Maybe a trend" or "No clear trend", with the change per decade, the total change and a 95% confidence interval. |
| **Two tests, not one** | A linear regression plus Mann-Kendall with the Hamed-Rao correction (so a year that resembles the previous one can't fake a trend). |
| **Is it steady?** | The record is split into thirds: is the change speeding up, slowing down, or reversing? Also a "big vs real" grid, because a large change can still be uncertain. |
| **Opposite trends in one box** | Every grid cell inside the box is tested on its own and coloured on the globe (rising / falling / not clear). One average can hide cells moving in opposite directions. |
| **Second witness** | For temperature and rain, the nearest long-running NOAA weather station is tested the same way. Agreement makes the result stronger; disagreement is flagged (e.g. Kolkata rain: the reanalysis rises, the Dum Dum gauge doesn't). |
| **Full check-up** | One click tests 8 variables at the same place and gives a rule-based label such as *"cooling, more humid-heat days, getting wetter, losing green"*. No AI in that label. |
| **Compare** | Pin a result, then click another place or variable; both are drawn on one chart (second axis when units differ). |
| **Case files** | 12 ready-made investigations: Svalbard warming, Arctic sea ice, North India's opposite trends, Pearl River chlorophyll, Dhaka's humid heat, greening and browning Bangladesh districts and more. |
| **Time machine** | NASA GIBS satellite imagery for each year plays on the globe while the chart follows along. Natural events from NASA EONET (fires, storms, floods) are marked. |
| **AI coach** *(optional)* | Ask "explain this simply" or your own question. The server recomputes the numbers itself and Claude may only use those numbers, keeping evidence separate from possible explanations. |
| **CSV export** | Download the exact numbers behind the chart. |

## NASA (and partner) data used

| Source | Variables | Access |
|---|---|---|
| **NASA POWER** (MERRA-2 + CERES), monthly, regional grid | Air temperature, max/min, rain, soil wetness, evaporation, sunshine, humidity, snow, sea ice, aerosol… 1981–2025 | API, no login |
| **NASA POWER** daily | Days above 35 °C, humid-heat days (wet-bulb ≥ 26 °C) | API, no login |
| **MODIS** MOD13Q1 / MOD11A2 (Terra) | Vegetation greenness (NDVI), land surface temperature | ORNL DAAC subset API; 64 Bangladesh districts pre-extracted |
| **MODIS-Aqua ocean colour** (OB.DAAC) | Ocean chlorophyll, 2003–2025, yearly, regridded to 0.5° | Earthdata Cloud, pre-processed into `app/data/chl_yearly.npz` |
| **GISTEMP**, **NSIDC Sea Ice Index**, **PO.DAAC** | Global temperature, Arctic/Antarctic sea ice, sea level | Public CSV |
| **NASA GIBS / Worldview** | Satellite imagery on the globe, "open in Worldview" links | Public tiles |
| **NASA EONET** | Natural events on the timeline | Public API |
| **NOAA NCEI GSOM** | Weather-station monthly records (second witness) | Public API |

`research/` holds the pre-hackathon data research: `catalog.json` (37 variables with exact dataset IDs and access routes) and `README.md` (every endpoint tested, gotchas, example trend results).

## Run it

Needs Python 3.12+ (developed on 3.14).

```bash
python -m venv .venv
.venv/Scripts/pip install -r requirements.txt        # Windows
# .venv/bin/pip install -r requirements.txt          # macOS / Linux
python -m uvicorn app.server:app --port 8000
```

Open <http://localhost:8000>. Most variables need no login at all.

### Optional keys (`.env` in the project root, never committed)

```
EARTHDATA_TOKEN=...      # NASA Earthdata Login token: only needed to rebuild the chlorophyll grid (app/build_chl.py)
ANTHROPIC_API_KEY=...    # turns on the AI coach; without it the coach panel says it is switched off
```

### Tests

```bash
python -m app.test_trends
python -m app.test_events
```

## How it works

```
app/
  server.py        FastAPI: fetches NASA data, runs the trend tests, serves the page
  trends.py        Statistics: yearly means, OLS + Mann-Kendall + Hamed-Rao, thirds, warnings, plain-language text
  build_chl.py     One-off: MODIS-Aqua yearly chlorophyll -> 0.5° grid (app/data/chl_yearly.npz)
  data/            Pre-processed data (Bangladesh district MODIS, chlorophyll grid)
  static/          index.html, app.js, style.css: CesiumJS globe + Plotly chart, no build step
research/          Data research done before the hackathon
```

- **Server-side only secrets:** tokens and keys stay in `.env` on the server and are never sent to the browser.
- **Disk cache:** every NASA response is cached in `cache/`, so a demo works on bad Wi-Fi once a place has been opened.
- **Honest statistics:** short records, autocorrelation, direction changes and yearly-only datasets each produce a plain-language warning instead of a confident wrong answer.

## AI disclosure

- The optional **AI coach** uses **Claude (Anthropic)** to explain results in plain English or Bangla. It is given only numbers the server computed and is told never to invent values or claim causes. The panel labels its answers as AI-written.
- AI coding assistance (Claude Code) was used while building this project.
- Trend verdicts, the check-up label and all numbers come from fixed statistics and rules, not from AI.

## Team and credits

- Built for NASA Space Apps Challenge 2026.
- Ideas and Bangladesh district MODIS data merged from teammates' projects **TerraBangla** (Bangla interface, district data, check-up idea) and **GlobtraceX** (UI ideas).
- Imagery: NASA GIBS. Borders and places: Natural Earth. Globe: CesiumJS. Charts: Plotly.
