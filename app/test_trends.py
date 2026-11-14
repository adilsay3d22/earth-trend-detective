"""Smallest check that the trend logic tells signal from noise. Run: .venv/Scripts/python.exe -m app.test_trends"""
import numpy as np

from app.trends import analyse, num, yearly

rng = np.random.default_rng(1)
yrs = list(range(1981, 2026))

warm = analyse(yrs, 0.03 * (np.array(yrs) - 1981) + rng.normal(0, 0.15, len(yrs)), "Air temperature", "°C", "in Test box")
assert warm["level"] == "significant" and 0.2 < warm["slope_per_decade"] < 0.4, warm
assert warm["verdict"].startswith("Air temperature in Test box rose by"), warm["verdict"]
ramp = [10 + i for i in range(len(yrs))]
assert "%" in analyse(yrs, ramp)["verdict"] and "%" not in analyse(yrs, ramp, anomaly=True)["verdict"]
assert "%" not in analyse(yrs, ramp, unit="°C")["verdict"]           # % of a Celsius value is meaningless
assert "p = " not in warm["meaning"] + " ".join(warm["facts"]) and "p = " in " ".join(warm["details"])  # jargon stays in details

flat = analyse(yrs, rng.normal(10, 1, len(yrs)), "Rain", "mm/day")
assert flat["level"] == "none" and "not clearly changed" in flat["verdict"], flat["verdict"]
assert "lost in the natural ups and downs" in flat["facts"][0], flat["facts"][0]

rev = analyse(yrs, [abs(y - 2003) * -0.1 for y in yrs])          # up then down
assert any("Direction changed" in w for w in rev["warnings"]), rev["warnings"]
assert "not the same in every part" in rev["stability"] and len(rev["periods"]) == 3

assert warm["quadrant"]["real"] and warm["quadrant"]["big"], warm["quadrant"]
assert not flat["quadrant"]["real"] and flat["quadrant"]["label"].startswith("Lost in the noise")
fast = analyse(yrs, [(y - 1981) ** 2 * 0.01 for y in yrs])            # accelerating
assert "faster in the latest years" in fast["stability"], fast["stability"]

assert "error" in analyse([2000, 2001, 2002], [1, 2, 3])
assert "every year" in analyse(yrs, [0.0] * len(yrs), "Sea ice", region="in the tropics")["error"]   # no ice, no test

y, v = yearly([["2000-01", 1], ["2000-02", 3], ["2001-09", 5]], month=0, min_months=2)
assert (y, v) == ([2000], [2.0])
assert yearly([["2000-09", 4], ["2001-09", 6], ["2001-08", 0]], month=9) == ([2000, 2001], [4.0, 6.0])
assert num(0.0123) == "0.0123" and num(1234.5) == "1,234" and num(-0.5) == "-0.500"
print("trends OK")
