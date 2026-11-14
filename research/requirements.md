# Earth Trend Detective: feature list and requirements

*Planning document, 2026-11-12. No app code exists yet: the build starts at the Nov 14 kickoff (Space Apps rule, see [README.md](README.md)). Every layer, date range and number below was checked live today. Exact IDs and access routes are in [catalog.json](catalog.json) (33 variables, 11 sources).*

## 1. What we're building

One web app with two connected modes:

- **Investigate** is the guided detective flow. You pick a place and a variable, then get the evidence chart and a verdict: is it changing, by how much, and is the change real?
- **Time Machine** is a 3D globe. You pick **any** variable in the catalog (temperature, rain, haze, snow, greenness, sea ice, soil water...) and a year range such as 2000–2026, then press play. The Earth changes frame by frame while a chart, a counter and fact captions update alongside.

Both modes run on the same engine: one variable catalog, one set of trend tests, and one rule: every number on screen comes from NASA data, with its source shown.

The two modes link to each other. Clicking a spot on the playing globe opens Investigate with that region and variable already filled in, and every verdict card has a "Watch it on the globe" button.

**Users:** high-school and college students, teachers and the public. **Judges** see it through a short demo video and the project page.

## 2. Feature list

**Must** = in the demo no matter what. **Should** = planned for the 48 hours. **Could** = only if time allows. **Won't** = out of scope.

### Time Machine (globe)

| ID | Feature | Priority |
|---|---|---|
| T1 | 3D globe with NASA imagery: rotate and zoom, with both poles visible | Must |
| T2 | Variable picker covering every catalog variable, grouped Heat / Water / Ice / Air / Life, with a plain definition | Must |
| T3 | Year-range filter (from, to), limited to the years the dataset covers; the slider shows that coverage | Must |
| T4 | Play, pause, speed and scrub controls, with a big date label on every frame | Must |
| T5 | Frame step: same month each year (default), annual mean, or every month | Must |
| T6 | **Look** view: real NASA imagery for each date, from GIBS | Must |
| T7 | Synced chart: the region's series draws as the globe plays, with a cursor on the current frame | Must |
| T8 | Live counter: current value vs the start of the range, absolute and in % | Must |
| T9 | Auto facts: captions generated from the data during playback (records, big jumps, gaps, trend verdict) | Must |
| T10 | Region: whole globe or a box drawn on it; the chart, counter and facts follow the region | Should |
| T11 | **Change** view: difference from the first years of the range, so small trends become visible | Should |
| T12 | **Trend** view: one map of the trend at every pixel over the range, with non-significant areas dotted | Should |
| T13 | Then-vs-now split slider (first frame vs last frame) | Should |
| T14 | Compare: two variables or two regions playing in sync (for example haze over China vs India, or ice mass vs sea level) | Could |
| T15 | Altitude slider for the 3D atmosphere (850 hPa up to 50 hPa) | Could |
| T16 | "Today" button: the latest daily true-colour image | Could |
| T17 | Export the playback as a GIF or video | Could |

### Investigate (detective flow)

| ID | Feature | Priority |
|---|---|---|
| I1 | Where? Draw a box, pick a preset place, or choose a type of place (Arctic, desert, city...) | Must |
| I2 | What? Variable picker that suggests variables for that type of place (catalog `good_for`) | Must |
| I3 | Evidence chart: monthly values, seasonal cycle removed, annual means, trend line with 95% band | Must |
| I4 | Trend tests: linear fit with t-test and 95% CI, Mann-Kendall, Hamed-Rao (year-to-year memory), Sen slope | Must |
| I5 | Verdict card: what, where, how much and is it real, in a sentence a 15-year-old understands | Must |
| I6 | Proof panel: dataset name, DOI, and links to Worldview and Earthdata Search for the same place and time | Must |
| I7 | Season picker: whole year or one season, because a trend can hide in one season | Should |
| I8 | Second witness: the same question answered by an independent NASA dataset, with agreement shown | Should |
| I9 | Detective warnings: record too short, year-to-year memory, a break or reversal, sources disagree | Should |
| I10 | Global context strip: how much the whole planet warmed over the same years (GISTEMP) | Should |
| I11 | "How long until we'd know?": years of data needed to detect a trend of this size | Could |
| I12 | Place-name search | Could |

### Shared

| ID | Feature | Priority |
|---|---|---|
| S1 | Case files: ready-made investigations that open both modes at the right place, variable and years (§5) | Must |
| S2 | Offline demo: case-file data cached locally, plus a screen-recording fallback | Must |
| S3 | Glossary of trend, anomaly, significance, p-value and similar terms, in plain words | Should |
| S4 | Shareable URL that restores the exact view | Should |
| S5 | Download the data behind any chart as CSV | Could |
| S6 | SI assistant that answers questions using only computed numbers and the catalog, disclosed in the submission | Could |

### Won't (this hackathon)

- User accounts (our tokens stay on our server)
- Forecasts or ML predictions of the future
- Simulated "what if" scenarios such as drawn flooding (we show measured data only)
- Bulk downloads of raw datasets
- A native mobile app
- Variables beyond the catalog

## 3. Time Machine requirements

### 3.1 Screen

```
+--------------------------------------------------------------+
| [Variable v  Heat/Water/Ice/Air/Life]   [2000 ====o==== 2026] |
| [Step: same month each year v]   [View: Look | Change | Trend] |
+-----------------------------------------+--------------------+
|                                         |  SEPTEMBER 2012    |
|               3D GLOBE                  |  value now         |
|   drag to rotate, draw a box to select  |  change since 2000 |
|                                         |  ----------------  |
|                                         |  fact caption      |
|                                         |  verdict so far    |
+-----------------------------------------+--------------------+
| > ||  1x   chart: series draws as it plays, cursor on frame  |
| Source: dataset name - DOI - open in Worldview               |
+--------------------------------------------------------------+
```

### 3.2 Any variable: where the frames come from

The globe has to work for every catalog variable. There are three frame sources, and each variable uses whichever ones it has:

| Source | Gives | Covers | Cost |
|---|---|---|---|
| **GIBS tiles** (Look view) | NASA's own rendered imagery for each date | About 40 long-running layers (§3.3) | None: tiles stream from NASA with no login |
| **MERRA-2 via OPeNDAP** (Change and Trend views) | Monthly grids we subset and colour ourselves | Every MERRA-2 variable (temperature, humidity, rain, snow, soil water, wind, cloud, aerosol, dust, ozone), 1980–2026 | One request per frame, using the method in README §2b (561 months in 148 s). "Same month each year" needs about 46 requests |
| **Dataset grids** | Things MERRA-2 doesn't have | NSIDC sea-ice maps (1978–), GRACE ice/water mass grid (2002–), GISTEMP temperature grid (1880–), MODIS for a box via AppEEARS | Precompute for case files |

If a variable has no frames for part of the chosen years, the slider shows that part greyed out and the app explains why instead of failing.

### 3.3 Verified layers by theme (GIBS, checked 2026-11-12)

| Theme | Variables | GIBS layer(s) | Years | Step |
|---|---|---|---|---|
| Heat | Air temp (2 m), skin temp, upper air | `MERRA2_2m_Air_Temperature_Monthly`, `MERRA2_Surface_Skin_Temperature_Monthly`, `MERRA2_Air_Temperature_250hPa_Monthly` | 1980-01 to 2026-08 | month |
| Heat | Land surface temp | `MODIS_Terra_L3_Land_Surface_Temp_Monthly_Day` | 2000-03 to 2026-10 | month |
| Heat | Sea surface temp (already an anomaly) | `GHRSST_L4_MUR25_Sea_Surface_Temperature_Anomalies` | 2002-09 to now | day |
| Water | Rain | `MERRA2_Precipitation_Bias_Corrected_Monthly`, `IMERG_Precipitation_Rate` | 1980 / 2000-06 to now | month / day |
| Water | Water vapour, humidity | `MERRA2_Total_Precipitable_Water_Vapor_Monthly`, `AIRS_L3_Surface_Relative_Humidity_Monthly_Day` | 1980 / 2002-09 to 2026 | month |
| Water | Soil moisture, evaporation | `MERRA2_Soil_Water_Root_Zone_Monthly`, `GLDAS_Underground_Soil_Moisture_Monthly`, `MERRA2_Evaporation_Land_Monthly` | 1980 / 2000 to 2026 | month |
| Water | Sea surface salinity | `SMAP_L3_Sea_Surface_Salinity_CAP_Monthly` | 2015-04 to 2026-09 | month |
| Ice | Sea ice | `GHRSST_L4_MUR_Sea_Ice_Concentration` | 2002-06 to now | day |
| Ice | Snow cover, snowfall | `MODIS_Terra_L3_Snow_Cover_Monthly_Average_Pct`, `MERRA2_Snowfall_Monthly` | 2000-03 / 1980 to 2026 | month |
| Air | Haze (aerosol), dust | `MERRA2_Total_Aerosol_Optical_Thickness_550nm_Extinction_Monthly`, `MERRA2_Dust_Surface_Mass_Concentration_Monthly` | 1980 to 2026-08 | month |
| Air | Carbon monoxide, methane | `AIRS_L3_Carbon_Monoxide_500hPa_Volume_Mixing_Ratio_Monthly_Night`, `AIRS_L3_Methane_400hPa_Volume_Mixing_Ratio_Monthly_Night` | 2002-09 to 2026-09 | month |
| Air | SO2, ozone, UV | `MERRA2_SO2_Column_Mass_Density_Monthly`, `MERRA2_Ozone_Mixing_Ratio_50hPa_Monthly`, `OMI_UV_Erythemal_Daily_Dose` | 1980 / 2004 to 2026 | month / day |
| Life | Vegetation greenness | `MODIS_Terra_L3_NDVI_Monthly`, `MODIS_Terra_L3_EVI_Monthly` | 2000-03 to 2026-10 | month |
| Energy | Surface albedo, cloud, sunlight | `MERRA2_Surface_Albedo_Monthly`, `MERRA2_ISCCP_Cloud_Albedo_Monthly`, `MERRA2_Incident_Shortwave_Over_Land_Monthly` | 1980 to 2026-08 | month |
| Any | True-colour photo | `MODIS_Terra_CorrectedReflectance_TrueColor` (2000-02 on), `MODIS_Aqua_CorrectedReflectance_TrueColor` (2002-07 on) | daily | day |

**Don't use these for 2000–2026 playback.** They stop early or have gaps:
- `GRACE_Tellus_*`: ends 2022-07 (make frames from the GRACE grid instead).
- `JPL_MEaSUREs_L4_Sea_Surface_Height_Anomalies`: ends 2019-01.
- `AMSRE_*` / `AMSRU2_Sea_Ice_*`: 9-month gap from 2011-10 to 2012-07.
- `MISR_*`: ends 2022.
- Any `VIIRS_SNPP_*`: S-NPP stopped delivering data on 2026-11-02.

Tile URL: `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/{Layer}/default/{YYYY-MM-DD}/{TileMatrixSet}/{z}/{y}/{x}.png`. The TileMatrixSet for each layer (2km, 1km, 500m...) is listed in the capabilities file.

**Tile grid gotcha (checked in the capabilities file):** GIBS geographic tiles are 512 px. At level 0 there are 2×1 tiles, each 288° wide, so the grid covers longitude −180…396 and latitude 90…−198. A standard geographic tiling scheme (two 180° tiles) puts the imagery in the wrong place. In Cesium, use `GeographicTilingScheme({rectangle: Rectangle.fromDegrees(-180, -198, 396, 90), numberOfLevelZeroTilesX: 2, numberOfLevelZeroTilesY: 1})`. Tiles outside the real matrix just 404.

**Legends come free:** every layer we checked lists an SVG legend (`LegendURL`) and a colour-map XML in the capabilities file. NASA's colour scale is fixed across dates, so the Look view meets rule 2 in §3.4 with no work.

### 3.4 Playback rules (these keep it honest, which the Validity score rewards)

1. **Same month each year by default.** Playing Jan, Feb, Mar... mostly shows the seasons, which are far bigger than any trend. The default is one frame per year for the month that matters for that variable (for example September for Arctic ice, or the dry season for greenness), or the annual mean. Users can switch to every month.
2. **One fixed colour scale** for the whole playback, with a legend. Rescaling per frame would invent change.
3. **Small changes go in the Change view.** One degree of warming is invisible on a −40 to +40 °C palette. Temperature-type variables open in the Change view (difference from the first 5 years of the range) by default.
4. **Real frames only.** A short fade between two real frames is fine; making up in-between data is not. Missing data appears as a labelled "no data" frame, for example the GRACE gap from Jul 2017 to May 2018.
5. **Label partial years**, for example "2026, Jan–Sep". Monthly layers lag 1–3 months, and the slider says so.
6. **Speed** ranges from 0.5 to 4 frames per second. The default is 1, so 2000 to 2026 plays in about 27 s.
7. **Preload** the frames before playing, with a progress bar, so the demo doesn't flicker.
8. **Reduced motion:** with `prefers-reduced-motion`, frames step without fades and playback only starts on a click.

### 3.5 Insights and facts (generated, so they work for any variable)

Captions come from templates filled with the region's series. Each one is a computed number plus its source. `{...}` is filled in at run time; the examples marked ✓ are real results from today.

| Template | Example |
|---|---|
| Change since start | "Since {start}, {variable} here {rose/fell} {x} ({pct}%)." ✓ dry-season greenness, Rondônia: fell 18% |
| Trend with confidence | "{slope} per decade, 95% range {lo} to {hi}." |
| Is it real? (plain words) | "Very unlikely to be chance (p < 0.001)." / "Could be chance (p = {p}). See case file 'Is it real?'" |
| Record (pops up on that frame) | "{date}: lowest in this range ({value})." ✓ Arctic Sep 2012: 3.57 M km² |
| Ranking | "{n} of the {N} {highest/lowest} years came after {year}." |
| Biggest jump | "Largest one-year change: {y1} to {y2}." |
| Honesty check | "Not every year is worse: {k} of {N} years went the other way." |
| Global context | "Over the same years, the whole planet warmed {dT} °C (GISTEMP)." |
| Gaps | "No satellite data {from} to {to} ({reason})." |

Each variable also shows its plain definition, its unit in plain words, and one line on why it matters (catalog fields). Hand-written facts, such as "362 Gt of ice = 1 mm of global sea level", are allowed only with a citation stored next to them.

### 3.6 Regions

- **Whole globe:** the series is the area-weighted mean of the same grid (a hemisphere mean for polar variables).
- **Drawn box:** the series is the cos(latitude)-weighted mean inside the box, and the globe dims outside it.
- **Look view:** GIBS images are pictures, not numbers, so the chart uses the variable's numeric route from the catalog. If that is a different dataset from the imagery, the panel says so.

### 3.7 What "live" means

The globe streams NASA imagery from GIBS directly, with no copies. Daily layers are 1–3 days behind and monthly layers 1–3 months behind. "Today" means the newest day available. We don't call it real-time.

## 4. Investigate requirements

- **Data tiers:**
  - NASA POWER first: instant, no login, 1981–2025, box 2–10° in each direction.
  - Giovanni / Harmony area averages: seconds to minutes, needs the token.
  - OPeNDAP for MERRA-2 grids and pressure levels.
  - AppEEARS for MODIS boxes: about 48 min per job, so precompute only.
- **Tests:** run on annual (or seasonal) means:
  - OLS slope with a two-sided t-test and 95% CI
  - Mann-Kendall
  - Hamed-Rao modified MK, when lag-1 autocorrelation matters
  - Sen slope
- **Verdict:** "significant" when the (Hamed-Rao) MK p < 0.05, "borderline" for p between 0.05 and 0.10, otherwise "not distinguishable from chance". Non-significant results are shown just as plainly as significant ones; the brief says they're interesting too.
- **Verdict sentence:** "{Variable} in {place} {rose/fell} by {x} per decade from {y0} to {y1} ({pct}% overall). {Plain significance}."
- **Warnings fire when:**
  - there are fewer than 15 years of data
  - the naive p and the Hamed-Rao p disagree on significance
  - the first-half and second-half slopes have opposite signs (a reversal)
  - the second witness disagrees in sign or significance
  - more than 10% of the data is missing
- **Second-witness pairs**, from the catalog's multiple routes per variable, for example:
  - POWER rain vs GPM IMERG (verified: Sahel r = 0.82)
  - POWER skin temperature vs MODIS LST
  - MERRA-2 aerosol vs MODIS AOD
- **Years to detect** (Weatherhead et al. 1998): n ≈ [(3.3 σ / |trend per year|) × √((1+φ)/(1−φ))]^(2/3), where σ is the noise standard deviation and φ the lag-1 autocorrelation.

## 5. Case files (demo stories across all themes)

| # | Story | Theme | Shown in | Variable, region, years | Verified result |
|---|---|---|---|---|---|
| 1 | Up is down | Heat / Air | Time Machine (altitude) + Investigate | MERRA-2 temperature at 850 vs 50 hPa, global, 1980–2025 | +0.20 vs −0.30 K per decade |
| 2 | Two hazes | Air | Time Machine compare | Aerosol, East China vs Indo-Gangetic Plain, 1981–2025 | China +0.17 until 2011 then −0.26; India +0.086 per decade |
| 3 | The trend hides in one season | Life | Both | MODIS NDVI in the dry season, Rondônia, 2001–2025 | 0.725 → 0.595 (p < 1e-6); wet season no trend |
| 4 | Delhi's cooling afternoons | Heat | Investigate | Daily max temperature + sunlight + humidity, Delhi | −0.31 °C per decade |
| 5 | Is it real? | Ocean heat | Investigate | Sea-surface temperature, North Atlantic warming hole | p = 0.02 naive, 0.17 Hamed-Rao |
| 6 | Arctic amplification | Heat / Ice | Time Machine (Change view) | Air temperature + sea ice, Svalbard / Barents | +0.68 °C per decade; ice −5 points per decade |
| 7 | The rains came back | Water | Investigate + second witness | Jul–Sep rain, Sahel | +37%; POWER vs GPM r = 0.82 |
| 8 | Megadrought | Water | Both | Root-zone soil water, Arizona vs interior Spain | −8% (p = 0.002) vs no trend (p = 0.45) |
| 9 | Ice → sea | Ice / Water | Time Machine compare | Arctic Sept ice, Greenland + Antarctic mass, global sea level | See below |

Story 9 numbers:
- Arctic September ice: 6.25 M km² in 2000, 4.81 M km² in 2026, record low 3.57 M km² in 2012.
- Greenland lost 6,086 Gt from 2002 to 2026, which adds 16.8 mm to global sea level. Antarctica lost 2,492 Gt, adding 6.9 mm.
- Global sea level rose 84 mm from 2000 to 2025.
- The teaching point: floating sea ice melting does not raise sea level; ice on land does.

The demo video uses three of these; the team picks at kickoff (§11). A good spread is #1 as the opener, #2 as the Time Machine "wow", and #3 or #9.

## 6. Data requirements

- **Source of truth:** [catalog.json](catalog.json). Every variable the app offers has an entry with a plain definition and at least one access route. At kickoff, add three fields per variable:
  - `timelapse`: GIBS layer, default step and month
  - the MERRA-2 collection and variable name for Change frames
  - `doi`
- **Precompute on Saturday night:**
  - case-file series as JSON
  - Change and Trend frames for case-file variables
  - AppEEARS jobs
  - facts JSON

  Approximate sizes: NSIDC maps about 130 MB (2 months × 2 poles × 48 years), the GRACE grid 44 MB (one file), MERRA-2 coarse frames a few KB each.
- **On demand, for everything else:**
  - GIBS Look view: instant.
  - MERRA-2 Change frames through OPeNDAP: about 15–30 s the first time, then cached on disk.

## 7. Non-functional requirements

| Area | Requirement |
|---|---|
| Speed | Case files open in under 2 s (cached). A POWER investigation returns in under 5 s. A GIBS-layer playback starts within 5 s. |
| Reliability | The demo case files work with Wi-Fi off, and a recorded video is the last-resort fallback. |
| Security | `EARTHDATA_TOKEN` and `APPEEARS_TOKEN` live only in the server's `.env`. The browser talks only to our backend and to public GIBS tiles. Check the devtools network tab for tokens before submitting. |
| Plain language | Everything is readable by a 15-year-old, and every jargon term has a glossary tooltip. |
| Accessibility | Colour-blind-safe palettes for our own frames: sequential for amounts, diverging blue-red with a neutral middle for the Change view. Keyboard controls: Space plays or pauses, ←/→ step. The facts panel describes in text what the map shows. Reduced motion is respected. |
| Display | Chrome or Edge on a laptop, 1366×768 up to a 1920×1080 projector. A phone layout is Could. |
| Honesty | Every number traces to a dataset and date range. Non-significant results get equal billing. |
| Rules | Don't use the NASA logo; say "uses NASA data" (re-check the 2026 rules). Open-source licences only. Disclose SI use. Data citations go in the project README. |

## 8. Tech stack (recommended)

- **Globe: CesiumJS** (Apache-2.0). This replaces Leaflet from the earlier plan, so one map library serves both modes.
  - **It draws the poles.** Leaflet and MapLibre use Web Mercator tiles, which stop near 85° latitude and leave a hole at the Arctic. That hurts every high-latitude variable, not just ice.
  - **It plays GIBS time layers natively.** It reads GIBS's time-dimension WMTS with its own clock, so play, pause and speed come built in.
  - **No account needed** when GIBS is the base layer and the default terrain is skipped.
- **Our own frames:** equirectangular PNGs covering −180…180 and −90…90, shown as a single-tile layer and swapped each frame.
- **Charts:** Plotly.js.
- **Backend:** Python FastAPI with a disk cache. Endpoints: `GET /variables`, `/series`, `/trend`, `/layers` (frame manifest per variable), `/frame/{var}/{view}/{date}.png`, `/facts`.
- **Stats:** numpy, scipy, pymannkendall.
- **Precompute:** one Python script.

## 9. 48-hour plan

| When | Data / backend | Stats / science | Frontend / globe | Story / video |
|---|---|---|---|---|
| Sat AM | `/series` + `/trend` on POWER | Test functions and verdict logic | Cesium globe with one GIBS layer playing over a year slider | Pick case files, write fact templates |
| Sat PM | Giovanni / Harmony, OPeNDAP frames, cache | Warnings, second witness | Investigate flow, chart synced to the globe | Glossary and on-screen text |
| Sat night | Precompute case files, start AppEEARS jobs | Change and Trend frames | Change and Trend views | Storyboard the video |
| Sun AM | `/facts` | Years to detect | Facts panel, links between the modes, box selection | Record runs |
| Sun PM | Freeze the code | Check every on-screen number | Polish, accessibility | Video, README with citations and SI disclosure, submit |

**If behind, cut in this order:**
1. SI assistant
2. Compare (T14)
3. Altitude slider
4. AppEEARS
5. Trend view
6. Change view for non-case variables

**Never cut:** the verdict card, the significance tests, Time Machine Look view with the synced chart and facts, and sources/DOIs on screen.

## 10. Acceptance checklist (demo-ready when all are true)

- [ ] Pick any variable from §3.3, set 2000–2026 and press play: frames advance once per second with a date label, and the chart cursor and counter move in sync.
- [ ] Draw a box: the chart, counter and facts switch to that box.
- [ ] Air temperature in the Change view: the Arctic visibly stands out.
- [ ] A record frame shows its caption at the right moment.
- [ ] A variable with no data for part of the range shows a clear message.
- [ ] Clicking a spot opens Investigate with the same variable and region, with a verdict in under 5 s.
- [ ] Every screen shows the dataset and its DOI.
- [ ] With Wi-Fi off, the demo case files still play.
- [ ] No token appears anywhere in the browser.

## 11. Risks found in review (2026-11-12)

| Risk | What to do |
|---|---|
| POWER only takes boxes 2–10° wide, and its monthly data ends in 2025 | Boxes ≤10° within 1981–2025 use POWER. The whole globe, bigger boxes and 2026 months use the MERRA-2 OPeNDAP coarse grid (or a Harmony area average). |
| GIBS images are pictures, not numbers | MODIS-only variables (NDVI, snow cover, LST) get the Look view, plus AppEEARS box series for case files. Their Change and Trend views need a numeric MODIS grid that we haven't verified yet. Treat those as Could. |
| GIBS tile grid isn't the standard one | Use the custom tiling rectangle in §3.3. Test it first thing on Saturday. |
| AppEEARS token expires 2026-11-13 09:54 UTC | Log in again in Windows Terminal at kickoff (README §6). |
| The scratch Python is 3.14 | If a package lacks 3.14 wheels (netCDF4/h5py for the 44 MB GRACE file), use the OPeNDAP ASCII route or a 3.12 venv. |
| A public demo with our token could burn the Giovanni quota | The public build serves cached case files plus GIBS tiles; live Giovanni/AppEEARS calls only run locally. |

## 12. Decide at kickoff

- **Globe:** Cesium (recommended) or a 2D map.
- **Video:** which 3 case files go in it.
- **Team:** who owns which column of the plan (data/backend, stats/science, frontend/globe, story/video).
- **Rules:** re-read the 2026 judging and submission guides (out Nov 13) for video length and required links.
