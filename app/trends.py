"""Trend tests, plain-language verdict, warnings and data-driven facts. Pure functions, no I/O."""
import math

import numpy as np
import pymannkendall as mk
from scipy import stats


def yearly(monthly, month=0, min_months=10):
    """[["YYYY-MM", v], ...] -> (years, values). month=0: annual mean (needs min_months), else that month only."""
    by = {}
    for ym, v in monthly:
        y, m = int(ym[:4]), int(ym[5:7])
        if not month or m == month:
            by.setdefault(y, []).append(v)
    need = 1 if month else min_months
    years = sorted(y for y, v in by.items() if len(v) >= need)
    return years, [float(np.mean(by[y])) for y in years]


def num(v):
    """Short human number: 3 significant figures, no scientific notation unless tiny."""
    if v == 0 or not math.isfinite(v):
        return "0" if v == 0 else "n/a"
    if abs(v) < 1e-3:
        return f"{v:.2e}"
    digits = max(0, 2 - int(math.floor(math.log10(abs(v)))))
    return f"{v:,.{digits}f}"


def meaning(p):
    """What the p-value means, without saying p."""
    if p < 0.001:
        return "This is a clear, steady change. Normal ups and downs almost never make a pattern this strong."
    if p < 0.05:
        return "This looks like a real change. Normal ups and downs would rarely make a pattern this strong."
    if p < 0.10:
        return "There is a hint of a change, but normal ups and downs could still explain it. More years of data will tell."
    return "It goes up and down from year to year, but with no steady rise or fall. The natural swings are bigger than any trend."


def analyse(years, values, name="Value", unit="", region="here", anomaly=False):
    """region includes its preposition ("in the Arctic", "across the whole planet"). anomaly: values are
    differences from a baseline, so percentages make no sense."""
    x, y = np.asarray(years, float), np.asarray(values, float)
    n = len(x)
    if n < 8:
        return {"error": f"Only {n} years of data here: too short to test for a trend."}
    if np.ptp(y) == 0:
        return {"error": f"{name} {region} is {num(y[0])}{' ' + unit if unit else ''} every year, so there is nothing to test."}
    lr = stats.linregress(x, y)
    tcrit = stats.t.ppf(0.975, n - 2)
    fit = lr.intercept + lr.slope * x
    resid = y - fit
    s = math.sqrt(float(np.sum(resid ** 2)) / (n - 2))
    band = tcrit * s * np.sqrt(1 / n + (x - x.mean()) ** 2 / np.sum((x - x.mean()) ** 2))
    phi = float(np.clip(np.corrcoef(resid[:-1], resid[1:])[0, 1], -0.9, 0.9))
    mko, hr = mk.original_test(y), mk.hamed_rao_modification_test(y)
    p = float(hr.p) if math.isfinite(hr.p) else float(mko.p)
    level = "significant" if p < 0.05 else "borderline" if p < 0.10 else "none"
    up = lr.slope > 0
    y0, y1 = int(x[0]), int(x[-1])
    u = f" {unit}" if unit else ""

    per_dec, ci = lr.slope * 10, tcrit * lr.stderr * 10
    change = lr.slope * (x[-1] - x[0])
    sg = lambda v: "+" if v > 0 else ""
    pct = f" ({change / fit[0] * 100:+.0f}%)" if y.min() > 0 and fit[0] > 0 and not anomaly and unit not in ("°C", "K") else ""
    if level == "none":
        verdict = f"{name} {region} has not clearly changed from {y0} to {y1}."
    elif level == "borderline":
        verdict = f"{name} {region} may be {'rising' if up else 'falling'}: {sg(change)}{num(change)}{u}{pct} from {y0} to {y1}, but it is not certain yet."
    else:
        verdict = f"{name} {region} {'rose' if up else 'fell'} by about {num(abs(change))}{u}{pct} from {y0} to {y1}."

    facts = []
    if level == "none":
        facts.append(f"Single years jump around by about ±{num(s)}{u}, while the trend line moved only {sg(change)}{num(change)}{u} "
                     f"in {y1 - y0} years, so any change is lost in the natural ups and downs.")
    else:
        facts.append(f"That is about {sg(per_dec)}{num(per_dec)}{u} every 10 years. Single years still jump around the trend line by about ±{num(s)}{u}.")
    hi, lo = int(np.argmax(y)), int(np.argmin(y))
    facts.append(f"Highest year: {int(x[hi])} ({num(y[hi])}{u}). Lowest year: {int(x[lo])} ({num(y[lo])}{u}).")
    if level != "none":
        k = max(3, n // 5)
        top = np.argsort(-y if up else y)[:k]
        mid = int(x[n // 2])
        late = int(np.sum(x[top] >= mid))
        facts.append(f"{late} of the {k} {'highest' if up else 'lowest'} years came in {mid} or later.")
    d = np.diff(y)
    j = int(np.argmax(np.abs(d)))
    facts.append(f"Biggest one-year change: {int(x[j])} to {int(x[j + 1])} ({'+' if d[j] > 0 else ''}{num(d[j])}{u}).")
    against = int(np.sum(d < 0)) if up else int(np.sum(d > 0))
    if level != "none":
        facts.append(f"Not every year follows the trend: {against} of {n - 1} year-to-year steps went the other way.")
    omega = abs(float(mko.slope))
    n_star = ((3.3 * s / omega) * math.sqrt((1 + phi) / (1 - phi))) ** (2 / 3) if omega > 0 else math.inf

    details = [  # the science, for people who want it
        f"Trend: {sg(per_dec)}{num(per_dec)}{u} per decade (95% confidence range {num(per_dec - ci)} to {num(per_dec + ci)}).",
        f"p = {p:.2g}: the chance that random ups and downs alone would make a pattern this strong. Below 0.05 counts as "
        f"a significant trend. Test: Mann-Kendall with the Hamed-Rao correction for neighbouring years that resemble each other.",
        f"Sen's slope (ignores outliers): {sg(mko.slope)}{num(float(mko.slope) * 10)}{u} per decade. "
        f"Plain Mann-Kendall p = {mko.p:.2g}; straight-line fit p = {lr.pvalue:.2g}.",
    ]
    if math.isfinite(n_star):
        details.append(f"Detecting a trend this size reliably takes about {round(n_star)} years of data "
                       f"(Weatherhead et al. 1998); this record has {n}.")

    warnings = []
    if n < 15:
        warnings.append("Short record: fewer than 15 years. Natural ups and downs easily fool trends this short.")
    if mko.p < 0.05 <= p:
        warnings.append("Neighbouring years look alike here, which can make a random wander look like a trend. "
                        "A simple test calls it significant, but once we allow for that, it is not.")
    h = n // 2
    if h >= 6:
        s1, s2 = stats.linregress(x[:h], y[:h]).slope, stats.linregress(x[h:], y[h:]).slope
        if s1 * s2 < 0:
            warnings.append(f"Direction changed: the first half went {'up' if s1 > 0 else 'down'}, the second half "
                            f"{'up' if s2 > 0 else 'down'}. One straight line hides this.")
    missing = (y1 - y0 + 1) - n
    if missing > 0.1 * n:
        warnings.append(f"Missing years: {missing} years in this range have no data.")

    # Is it steady? Same tests on the early, middle and late thirds of the record.
    periods = []
    if n >= 15:
        for part in np.array_split(np.arange(n), 3):
            m = mk.original_test(y[part])
            periods.append({"from": int(x[part[0]]), "to": int(x[part[-1]]), "per_decade": float(m.slope) * 10, "p": float(m.p)})
    signs = {np.sign(q["per_decade"]) for q in periods}
    if not periods:
        stability = None
    elif len(signs) > 1:
        stability = "The direction is not the same in every part of the record, so the overall trend depends on which years you pick."
    elif abs(periods[-1]["per_decade"]) > 1.5 * abs(periods[0]["per_decade"]):
        stability = "It goes the same way in every part of the record, and faster in the latest years."
    elif abs(periods[-1]["per_decade"]) < abs(periods[0]["per_decade"]) / 1.5:
        stability = "It goes the same way in every part of the record, but more slowly in the latest years."
    else:
        stability = "It goes the same way, at a similar speed, in every part of the record."

    # Significant vs big: the change along the trend line compared with how much single years jump around.
    big, real = abs(change) >= s, level == "significant"
    quadrant = {"big": bool(big), "real": real, "label": {
        (True, True): "Big and real: the change is larger than the normal year-to-year swings, and it is very unlikely to be chance.",
        (False, True): "Small but real: steady enough to be very unlikely to be chance, yet still smaller than the normal year-to-year swings.",
        (True, False): "Big but uncertain: the line moved more than the normal swings, but the years are too jumpy or too few to be sure.",
        (False, False): "Lost in the noise: any change is smaller than the normal year-to-year swings.",
    }[(bool(big), real)]}

    return {
        "verdict": verdict, "level": level, "meaning": meaning(p), "details": details,
        "periods": periods, "stability": stability, "quadrant": quadrant,
        "slope_per_decade": per_dec, "ci_per_decade": ci, "sen_per_decade": float(mko.slope) * 10,
        "p_ols": float(lr.pvalue), "p_mk": float(mko.p), "p_hamed_rao": p, "lag1": phi,
        "years_to_detect": n_star if math.isfinite(n_star) else None,
        "fit": fit.tolist(), "band": band.tolist(), "facts": facts, "warnings": warnings,
    }
