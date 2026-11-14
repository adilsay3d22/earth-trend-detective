"""One-off: yearly MODIS-Aqua chlorophyll maps (9 km) -> app/data/chl_yearly.npz on a 0.5 deg grid.
Each 0.5 deg cell is the log-mean of its 6x6 ocean pixels (chlorophyll is log-normal; Acker et al. 2009 work in log space).
Run: .venv/Scripts/python.exe -m app.build_chl   (downloads ~15 MB per year from the OB.DAAC cloud, needs EARTHDATA_TOKEN)"""
import io
import pathlib

import h5py
import numpy as np
import requests

ROOT = pathlib.Path(__file__).resolve().parent.parent
ENV = dict(l.split("=", 1) for l in (ROOT / ".env").read_text().splitlines() if "=" in l)
H = {"Authorization": f"Bearer {ENV['EARTHDATA_TOKEN'].strip()}"}
URL = "https://obdaac-tea.earthdatacloud.nasa.gov/ob-cumulus-prod-public/AQUA_MODIS.{y}0101_{y}1231.L3m.YR.CHL.chlor_a.9km.nc"
OUT = ROOT / "app" / "data" / "chl_yearly.npz"


def year_grid(y):
    r = requests.get(URL.format(y=y), headers=H, timeout=600)
    r.raise_for_status()
    with h5py.File(io.BytesIO(r.content)) as f:
        a = f["chlor_a"][:].astype("float32")                      # 2160 x 4320, north row first, -180 first column
    a[(a <= 0) | ~np.isfinite(a)] = np.nan
    blocks = np.log10(a).reshape(360, 6, 720, 6)
    ok = np.sum(np.isfinite(blocks), axis=(1, 3))
    with np.errstate(invalid="ignore", all="ignore"):
        g = np.nanmean(blocks, axis=(1, 3))
    g[ok < 6] = np.nan                                              # mostly land or cloud: no value
    return g.astype("float16")


if __name__ == "__main__":
    years = list(range(2003, 2026))                                 # Aqua's first and last full years
    grids = []
    for y in years:
        grids.append(year_grid(y))
        print(y, "ok", flush=True)
    np.savez_compressed(OUT, years=np.array(years), log10_chl=np.stack(grids))
    print(OUT, OUT.stat().st_size // 1024, "KB")
