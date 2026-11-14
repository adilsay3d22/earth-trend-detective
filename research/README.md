# NASA data research — Earth System Trend Detective

Research done 2026-11-12 (before the hackathon). Every endpoint below was hit live that day.
`catalog.json` is the structured version: 33 variables × exact IDs for every access route.
**What to build:** [requirements.md](requirements.md) has the feature list, the Time Machine globe spec (verified GIBS layers by theme), case files and the 48-hour plan.

> **Rule check:** the Space Apps FAQ says *"Teams are not allowed to begin working on the challenges prior to the hackathon."*
> This folder is research only (what data exists, how to reach it). No app code has been written. Start the build at your Local Event's kickoff on Nov 14.

---

## 1. The four portals you sent

| Portal | What it really is | Login? | How we use it |
|---|---|---|---|
| **[Worldview](https://worldview.earthdata.nasa.gov/)** | Map viewer on top of **GIBS**, 1,330 imagery layers (true colour, temperature, rain, NO₂, CO₂, snow, sea ice…). Pictures only, no numbers. | No | Map background and "see it from space" visuals. GIBS tiles plug straight into Leaflet. Add an **"Open in Worldview"** deep link: `?v=w,s,e,n&l=Layer&t=YYYY-MM-DD` (tested). |
| **[AppEEARS](https://appeears.earthdatacloud.nasa.gov/)** | Point/area extraction for **193 land products**: MODIS, VIIRS, SMAP, Landsat, ECOSTRESS, DEMs. An area request returns a **statistics CSV** (mean per date over your polygon). | Yes, for requests (product list is public) | Satellite land variables: NDVI, land-surface temperature, evapotranspiration, snow, burned area, SMAP soil moisture. It's async (minutes), so **precompute demo regions**. |
| **[GES DISC](https://disc.gsfc.nasa.gov/)** | Archive for **every dataset the challenge names** except MODIS: MERRA-2, GLDAS, GPM, AIRS, OMI, plus OCO-2 and GRACE. Has **Giovanni**. | Yes | The core trend engine (§3). |
| **[Earthdata Search](https://search.earthdata.nasa.gov/)** | UI over **CMR**, the metadata catalog of all NASA Earth data. Search, not analysis. | No (for search) | Variable discovery and definitions via the CMR API (`/search/variables.umm_json` returns long names and units). Add a **"Find the raw data"** link on every result to prove provenance. |

## 2. Extra sources I found

| Source | Why it matters | Login? |
|---|---|---|
| **NASA POWER API** | **Best hackathon fit.** Area-gridded monthly series 1981–2025 for 134 variables (MERRA-2 + CERES): temperature, Tmax/Tmin, rain, soil wetness, evapotranspiration, snow, sea ice, aerosol, humidity, sunlight, wind… JSON in about 2 seconds. | **None** |
| **Giovanni Area-Averaged Time Series** (via NASA Harmony, tutorial Apr 2026) | Give it a box, a variable and a date range; get back a CSV of the **area-mean time series**. This is the exact core operation of the challenge, for 867 variables: GPM, AIRS, OMI, GLDAS, MERRA-2, OCO-2, GRACE. | Yes + monthly quota |
| **Giovanni Time Series API** (point) | Same 867 variables, single point, CSV, synchronous. The public variable list is at `api.giovanni.earthdata.nasa.gov/configured-variables/`. | Yes (bearer token) |
| **GISTEMP** (NASA GISS) | Global, zonal and gridded temperature anomaly 1880–2026, CSV. Good as a context strip ("the globe warmed X in the same period"). | None |
| **NSIDC Sea Ice Index** (NASA DAAC) | Monthly Arctic/Antarctic extent 1978–2026, CSV. Sep 2026 Arctic extent: **4.81 M km²** (1979: 7.05). | None |
| **VEDA / Earth Information Center** | 247 collections, mostly single events. A few long series (FLDAS soil-moisture anomalies, OMI NO₂ annual). Secondary. | None |

**Verified with our own Earthdata token (Nov 12):**
- **Giovanni point series:** works. GPM monthly rain at a Sahel point came back as CSV in seconds, with a 13-line header (DOI, units, fill value).
- **Lag:** IMERG Final monthly runs about 3 months behind (asking for data through Dec 2025 returned data up to Sep 2025).
- **Harmony area average:** works. 25 years of monthly GPM over a 10°×3° box came back in **34 s**.
- **Giovanni quota:** `/quota` returned `0` (none used yet).
- **Cloud OPeNDAP subsetting of 3D MERRA-2:** works (see §2b).
- **AppEEARS:** rejects the Earthdata token (403). It needs its own token from `POST /api/login` with your username and password; ours lasted about 24 h.
  - **Verified with that token:** an area task for MOD13A3 NDVI (300 months, 1°×1°) returned `202` and finished in **48 min**.
  - **Statistics CSV:** the bundle includes `…-Statistics.csv` (Date, Count, Mean, Median, SD…). Parse it with a real CSV reader, because `Range` is a quoted `"(min,max)"`.

**Setup that unblocked it:** with only the token, GES DISC, OPeNDAP, Giovanni and Harmony all returned 403 or "invalid bearer token". Approving **"NASA GESDISC DATA ARCHIVE"** under Earthdata Login → Applications → Authorized Apps fixed all four instantly. No new token was needed.

**Gotchas found while probing:**
- **Hydrology Data Rods is retired.** It redirects to the new Giovanni Time Series Service. Old tutorials will break.
- **Suomi NPP stopped delivering data on Nov 2, 2026.** Use NOAA-20/21 VIIRS (`VJ1…` products) or MODIS for anything recent.
- **Terra MODIS ends science collection around Feb 2027, Aqua around Sep 2027.** The 2000–2026 archive stays, and VIIRS on NOAA-20/21 continues it. This is a good line for the pitch.
- **POWER regional boxes must span 2–10° in both lat and lon**, otherwise HTTP 422. Smaller areas use the point endpoint.
- **POWER `TO3` (ozone) has polar-night gaps.** Get ozone from OMI or AIRS via Giovanni.
- **POWER `IMERG_PRECTOT` has no monthly data.** Get GPM rain from Giovanni (`GPM_3IMERGM_07_precipitation`).

## 2b. 3D atmosphere (MERRA-2 pressure levels) — don't bulk-download

The Earthdata Search "download all" script for **M2I3NPASM** (3-hourly, 42 levels) has no filters. It would pull **17,076 files × ~1.16 GB ≈ 20 TB**, and it never sends credentials. Don't run it.

- The monthly version **M2IMNPASM** (collection `C1276812904-GES_DISC`) is 561 files × ~1.6 GB. Still too big to download.
- **Cloud OPeNDAP returns just a slice of each file.** For one variable, four levels and a coarse 4°×5° global grid, each month is a few KB:
  ```
  https://opendap.earthdata.nasa.gov/collections/C1276812904-GES_DISC/granules/M2IMNPASM.5.12.4%3AMERRA2_{100|200|300|400}.instM_3d_asm_Np.{YYYYMM}.nc4.ascii?T[0][6:10:36][0:8:360][0:8:575]
  ```
  The `T` index order is `[time][lev][lat][lon]`. The `[6:10:36]` stride picks levels 850, 500, 50 and 1 hPa. Header: `Authorization: Bearer <token>`.
- **Take granule URLs from CMR**, not by building them yourself. The stream number (100/200/300/400/401) changes by period.
- Values above 1e10 are fill (below ground, e.g. 850 hPa over Tibet or Antarctica). Mask them.
- The older GrADS Data Server (GDS) aggregation (`goldsmr5…/dods/`) is **gone (HTTP 410)**.
- **Performance:** all 561 months at 4 levels on a 4°×5° grid took **148 s** (8 parallel requests, about 20 KB each).
- **Output format:** `.ascii` rows look like `T.T[T.time=0][T.lev=850][T.lat=-90], v1, v2, …`.

### Result: vertical "same cause, opposite directions" ([figure](figures/atmosphere_levels.png))
| Level (global mean) | Trend 1980–2025, per decade | p (OLS) | Share of globe with a significant trend (MK) |
|---|---|---|---|
| 850 hPa (~1.5 km) | **+0.20 K** ±0.04 | 9e-14 | 76% warming, 1% cooling |
| 500 hPa (~5.5 km) | **+0.23 K** ±0.04 | 1e-13 | – |
| 50 hPa (~20 km) | **−0.30 K** ±0.09 | 3e-8 | **80% cooling**, 0% warming |
| 1 hPa (~48 km) | +0.32 K ±0.26 (artifact) | 0.02 | after 2005: **−0.99 K** (p = 1e-10) |

- **Physics:** more CO₂ traps heat low down and lets the upper atmosphere radiate more to space. That is the textbook fingerprint of greenhouse warming, and it's exactly the challenge's "one process, opposite trends" idea.
- **By region:**
  - Near the surface, the Arctic warms faster than the tropics (+0.38 vs +0.21 K/decade). Antarctica is flat (−0.07).
  - At 20 km, Antarctica cools fastest (−0.58 K/decade). That is the ozone-hole signature.
- **Events show up:** El Chichón (1982) and Pinatubo (1991) put warm spikes in the 50 hPa series, followed by a step down. Linear is a first look, not the full story.
- **Artifact lesson:** 1 hPa jumps about 3 K between 1999 and 2005, when the satellite instruments feeding MERRA-2 changed (AMSU, then Aura MLS in 2004). The full-record trend is wrong even in sign. The app should warn about breaks, for example by comparing the trend before and after the midpoint.

## 3. Recommended data architecture (3 tiers)

```
Tier 1  POWER (no login, instant)          → live demo, any box on Earth, 20 variables, 1981-2025
Tier 2  Giovanni area-average (token)      → the instruments the brief names: GPM, AIRS, OMI, GLDAS, MERRA-2, OCO-2, GRACE
Tier 3  AppEEARS area stats (own token, async) → MODIS/VIIRS/SMAP land: NDVI, LST, ET, snow, fire. Precomputed for demo regions.
3D      OPeNDAP subset of MERRA-2 M2IMNPASM (token)  → temperature/wind/humidity/ozone by altitude; ~2.5 min for 46 years, so cache it
Visual  GIBS tiles + Worldview link + Earthdata Search link → "NASA data, visibly"
```

The Earthdata token stays **server-side only**. It must never reach the browser or git.

## 4. Proof it works: 13 real trend tests

Pulled live from POWER (area-weighted box means). Each was tested four ways:
- **OLS t-test:** a straight-line fit, with a 95% confidence interval for the slope.
- **Mann-Kendall:** checks whether values keep rising or keep falling, without assuming a straight line.
- **Hamed-Rao modified Mann-Kendall:** the same test, corrected for each year resembling the previous one (autocorrelation).
- **Seasonal Mann-Kendall:** run on the monthly data, so the seasonal cycle is handled.

Yearly values are 1981–2025 unless noted.

| Region (box) | Variable | Trend per decade (±95% CI) | p (OLS / MK / Hamed-Rao) | Verdict |
|---|---|---|---|---|
| Barents Sea (74–78N, 32–42E) | Sea-ice fraction | **−0.051** ±0.018 | 1e-6 / 5e-6 / 3e-5 | Significant loss |
| Svalbard (76–80N, 10–20E) | Air temp | **+0.68 °C** ±0.21 (≈ +3 °C total) | 9e-8 / 4e-7 / 1e-14 | Significant warming |
| Labrador (52–56N, 66–58W) | Air temp | +0.46 °C ±0.26 | 7e-4 / 5e-3 / 0.04 | Significant warming |
| N. Atlantic "warming hole" (50–56N, 42–32W) | Sea-surface temp | +0.15 °C ±0.13 | 0.02 / 0.04 / **0.17** | **Not significant once autocorrelation is accounted for** |
| Rondônia, Amazon (12–9S, 64–60W) | Skin temp | +0.56 °C ±0.14 | 2e-10 / 3e-9 / 3e-9 | Significant warming |
| Alps, Dec–Apr (45.5–47.5N, 7–12E) | Snow cover | −0.023 ±0.021 (≈ −25%) | 0.03 / 0.02 / 0.01 | Significant, **borderline** |
| Arizona (32–35N, 113–110W) | Root-zone soil wetness | −0.0078 ±0.0048 (−8%) | 0.002 / 0.02 / 0.02 | Significant drying |
| Interior Spain (38–42N, 6–2W) | Root-zone soil wetness | +0.002 ±0.005 | 0.45 / 0.49 / 0.49 | **No trend** (honest null) |
| Sahel, Jul–Sep (12–15N, 5W–5E) | Rainfall | +0.41 mm/day ±0.17 (+37%) | 2e-5 / 4e-5 / 6e-6 | Significant: recovery from the 1980s drought |
| Indo-Gangetic Plain (25–28N, 78–85E), 2001–25 | Aerosol (AOD) | +0.086 ±0.015 (+32%) | 1e-11 / 5e-8 / ~0 | Significant: haze rising |
| Eastern China (30–34N, 114–120E), 2001–25 | Aerosol (AOD) | **+0.17 until 2011, then −0.26** | 0.008 then 5e-7 | **Trend reverses**; one straight line hides it |
| Delhi region (27.5–29.5N, 76–78E) | Daily max temp | **−0.31 °C** ±0.19 | 0.002 / 0.001 / 7e-4 | Afternoons getting *cooler* |
| Antarctic (85–75S) | Ozone (POWER) | Unusable: data gaps | – | Use OMI via Giovanni |

### Detective stories these give us (demo candidates)
1. **"Same cause, opposite directions" (the challenge's key point).** Air pollution from people: **East China haze falls** after its 2013 clean-air policy while **North India haze keeps rising**. Same variable, same kind of process, opposite trends. *(The brief calls this out directly.)*
2. **"Delhi's mystery cooling."** Daytime max temperature is *falling* while the Arctic warms 3 °C. The clues from other variables in the same box all point to haze and irrigation:
   - Sunlight reaching the ground: −0.39 MJ/m²/day per decade (p = 3e-5)
   - Humidity: +1.8% per decade
   - Aerosol: rising
   - Night-time minimum: not falling

   It's a multi-variable detective case, which fits the "data detective" goal well.
3. **"Is it real?"** The North Atlantic warming hole looks significant under a naive t-test (p = 0.02) but fails once you account for year-to-year memory (Hamed-Rao p = 0.17). This teaches *why* the test matters, and the brief says non-significant results are interesting too.
4. **Arctic amplification.** Svalbard +3 °C and Barents ice −5 points/decade, side by side with GIBS true-colour imagery from 2000 vs 2025.
5. **"Up is down" (probably the strongest opener).** The lower atmosphere warms and the stratosphere cools, both caused by CO₂ (§2b and the figure). It takes one picture to understand, and it's the brief's own idea applied vertically.
6. **"The trend hides in one season" (verified via AppEEARS, MODIS MOD13A3 NDVI, 1°×1° near Ariquemes, Rondônia, 14,400 pixels/month, 2001–2025).**
   - Dry-season (Jul–Sep) greenness fell **0.725 → 0.595** (−0.049/decade ±0.015, p < 1e-6 in all three tests).
   - Wet-season greenness shows **no trend** (p = 0.59), because cleared pasture looks as green as forest when it rains.
   - Pairs with POWER skin temperature in the same area (+0.56 °C/decade): two independent NASA records, one deforestation story.
   - AppEEARS took **48 min** for this one request, so precompute AppEEARS results.

### Cross-check done: Sahel rainfall, two independent NASA sources (Jul–Sep, 2001–2025, same box)
| Source | Trend per decade | p (OLS / MK) |
|---|---|---|
| MERRA-2 via POWER (reanalysis) | +0.73 mm/day ±0.43 | 0.002 / 0.002 |
| GPM IMERG via Giovanni + Harmony (satellites + gauges) | +0.35 mm/day ±0.32 | 0.03 / **0.07** |

The two agree on direction and on which years were wet or dry (**r = 0.82**). But the reanalysis trend is about **twice** as large, and the satellite trend is only borderline significant. This is exactly the kind of honesty judges reward: *"two NASA datasets agree it's getting wetter; how sure we are depends on which one you trust."* The app should show a second source whenever one exists.

> **Caveat for "Validity" points:** POWER is MERRA-2 *reanalysis*, which blends models and observations, and changes in the observing system can create fake trends. For each showcase, cross-check with a direct satellite record from Tier 2 or 3: GPM for rain, MODIS/OMI for aerosol, AIRS for temperature. Two independent NASA sources agreeing is a strong judging point.

## 5. My input: what will score well

**Judging criteria:** Impact, Creativity, Validity, Relevance, Presentation. The awards that fit best are Best Use of Science, Best Use of Data and Galactic Impact.

1. **Guided "detective" flow, not a data dump.** The user answers two questions:
   - *What do you care about?* Heat / water / ice / air / plants.
   - *Where?* Click the map, search a place, or pick a region type: desert, city, rainforest, Arctic, coast…

   `catalog.json → good_for` already maps region types to variables. Optional SI step: an LLM suggests variables and writes the plain-language "why". This must be disclosed in the submission.
2. **One result card that a 15-year-old understands:**
   - Arrow and rate: "Rising **0.68 °C per decade** (±0.21)"
   - Total change over the record
   - A green/amber/grey significance badge
   - Both tests agreeing: "Mann-Kendall agrees"
   - Plain-English warnings when relevant: *short record*, *values depend on the previous year*, *trend changes direction*
3. **The chart:**
   - Monthly raw values (faint)
   - Seasonal cycle removed (anomaly)
   - Yearly means
   - Trend line with a 95% CI band
   - Global GISTEMP as a context strip
4. **Compare mode:** two regions or two variables side by side. This is how the "opposite trends, same process" stories get told.
5. **Proof of NASA data on screen.** Every result shows:
   - Mission/model name and DOI
   - GIBS "then vs now" imagery
   - **Open in Worldview** and **Find in Earthdata Search** links
6. **2–3 canned demo cases** from §4, with results **cached locally**. Hackathon Wi-Fi fails, and AppEEARS and Harmony jobs are slow.
7. **Scope discipline.** The brief says linear trends and basic tests are enough. Add seasonal-cycle removal and a "compare halves" breakpoint hint only if time allows.

**Suggested stack (lean, 48 h):**
- **Backend:** FastAPI (Python). It does the fetching and the stats (`scipy`, `pymannkendall`) and holds the token.
- **Frontend:** single page with Leaflet (GIBS tiles) and Plotly.
- **Fallback:** if the team is Python-only, Streamlit gets there faster, but it is less polished for Presentation.

## 6. Do before Nov 14 (needs a human)

- [x] Earthdata Login account and token (in `.env`, valid until 2027-01-11, ignored by git).
- [x] Approved **"NASA GESDISC DATA ARCHIVE"**. Required for GES DISC, OPeNDAP, Giovanni and Harmony.
- [x] AppEEARS token (saved Nov 12, expires 2026-11-13 09:54 UTC, so **redo on Nov 14**). Run this in **Windows Terminal**, not the Claude app's Terminal panel: curl's password prompt doesn't wait for input there.
  ```powershell
  $r = curl.exe -s -X POST -u YOUR_EARTHDATA_USERNAME -H "Content-Length: 0" https://appeears.earthdatacloud.nasa.gov/api/login | ConvertFrom-Json; Add-Content E:\code\nasa\.env "`nAPPEEARS_TOKEN=$($r.token)"; "AppEEARS token saved, expires: $($r.expiration)"
  ```
  - **`expires:` with nothing after it means the login failed.** Remove the empty `APPEEARS_TOKEN=` line from `.env`, or remove the old token line before re-adding.
  - **Type the password only at the prompt.** Never type it at the PowerShell prompt or paste it into the command: PowerShell saves typed commands in `ConsoleHost_history.txt`.
- [ ] Nov 13: check the challenge **Resources** tab and the new Judging & Submission guides. Merge any new datasets into `catalog.json`.
