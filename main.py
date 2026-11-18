#!/usr/bin/env python3
"""Forecast a big game launch day's Twitch viewers, hour by hour.

Entry for make.fun's gta6-twitch-ccu-forecast-01 bounty. For every case
file in the input directory the program writes one forecast file with
five quantiles (5/25/50/75/95 %) for each of hours 2 to 24 of the
release day, given everything known up to the end of hour 1.

Method, in one paragraph: work on the log scale. Every past launch in
the case's `comparables` gives a curve of log-ratios ln(v_h / v_1).
Weight each launch by how similar it is to this case (size of its first
hour, and how far that first hour jumped above its own previous day).
For each forecast hour, read the quantiles of a weighted mixture of
narrow normals centred on those log-ratios, with one extra component
sitting at ratio 1 ("the audience just stays"), then scale back by
this case's first-hour count. Pure standard library, no randomness,
no network: the same input always gives the same output, byte for byte.
"""

import datetime as dt
import glob
import json
import math
import os

LEVELS = (0.05, 0.25, 0.5, 0.75, 0.95)

# Parameters fitted by leave-one-out over the practice comparables
# (see NOTES in the repository history): kernel widths for the size
# and jump features, the mixture's per-component spread at hour 2 and
# its growth per hour, the weight of the persistence component, and
# the smallest first hour a comparable needs to enter the pool.
PARAMS = {
    "bw_size": 0.9,
    "bw_jump": 1.2,
    "sd_base": 0.13,
    "sd_growth": 0.028,
    "w_stay": 0.35,
    "min_first_hour": 0.0,
}


def _ts(text):
    return dt.datetime.strptime(text, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc
    )


def _phi(x):
    """Standard normal CDF."""
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def _mixture_quantile(centres, weights, sd, tau):
    """Quantile of a weighted mixture of normals sharing one sd.

    Bisection on the mixture CDF; 90 halvings is far past float
    precision, so the result is deterministic.
    """
    total = sum(weights)
    lo = min(centres) - 8.0 * sd - 0.5
    hi = max(centres) + 8.0 * sd + 0.5
    for _ in range(90):
        mid = 0.5 * (lo + hi)
        cdf = 0.0
        for c, w in zip(centres, weights):
            cdf += w * _phi((mid - c) / sd)
        if cdf / total < tau:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _day_curve(comp):
    """One comparable launch, digested.

    Returns (first_hour, jump, {hour: log ratio to hour 1}) or None
    when the launch day is too incomplete to teach anything.
    """
    start = _ts(comp["day_start"])
    by_time = {}
    for row in comp["hourly"]:
        by_time[_ts(row["from"])] = row["viewers"]
    day = [by_time.get(start + dt.timedelta(hours=i)) for i in range(24)]
    if not day[0]:
        return None
    ratios = {}
    for h in range(2, 25):
        v = day[h - 1]
        if v:
            ratios[h] = math.log(v / day[0])
    if len(ratios) < 14:
        return None
    before = []
    for i in range(1, 25):
        v = by_time.get(start - dt.timedelta(hours=i))
        if v:
            before.append(v)
    jump = None
    if before:
        jump = math.log(day[0] / (sum(before) / len(before)))
    note = comp.get("unlock") or ""
    suspect = ("early-access" in note) or ("Tier: weak" in note)
    return {
        "first": float(day[0]),
        "jump": jump,
        "ratios": ratios,
        "suspect": suspect,
    }


def _pool(case):
    pool = []
    for comp in case["comparables"]:
        if "category before release" in comp["name"]:
            # The target game's own pre-release category history is
            # not a launch day; its shape would teach the wrong lesson.
            continue
        curve = _day_curve(comp)
        if curve is not None:
            pool.append(curve)
    return pool


def _case_features(case):
    first = float(max(case["known"][0]["viewers"], 1))
    start = _ts(case["day_start"])
    before = []
    for row in case.get("history_hourly") or []:
        t = _ts(row["from"])
        if start - dt.timedelta(hours=24) <= t < start and row["viewers"]:
            before.append(row["viewers"])
    jump = None
    if before:
        jump = math.log(first / (sum(before) / len(before)))
    return first, jump


def forecast(case, params=PARAMS, pool=None):
    if pool is None:
        pool = _pool(case)
    first, jump = _case_features(case)
    log_first = math.log(first)
    rows = []
    for spec in case["forecast"]:
        h = spec["hour"]
        centres = [0.0]
        weights = [params["w_stay"]]
        for curve in pool:
            if h not in curve["ratios"] or curve["first"] < params["min_first_hour"]:
                continue
            d_size = (math.log(curve["first"]) - log_first) / params["bw_size"]
            w = math.exp(-0.5 * d_size * d_size)
            if jump is not None and curve["jump"] is not None:
                d_jump = (curve["jump"] - jump) / params["bw_jump"]
                w *= math.exp(-0.5 * d_jump * d_jump)
            if curve["suspect"]:
                w *= 0.6
            if w > 1e-10:
                centres.append(curve["ratios"][h])
                weights.append(w)
        sd = params["sd_base"] + params["sd_growth"] * math.sqrt(h - 1)
        qs = []
        for tau in LEVELS:
            q = first * math.exp(_mixture_quantile(centres, weights, sd, tau))
            qs.append(q)
        for i in range(1, len(qs)):
            if qs[i] < qs[i - 1]:
                qs[i] = qs[i - 1]
        rows.append(
            {"hour": h, "q": [round(min(max(q, 0.01), 1e9), 4) for q in qs]}
        )
    return {"hours": rows}


def main():
    in_dir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(out_dir, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(in_dir, "*.in"))):
        with open(path, encoding="utf-8") as fh:
            case = json.load(fh)
        result = forecast(case)
        name = os.path.basename(path)[: -len(".in")]
        with open(os.path.join(out_dir, name + ".out"), "w", encoding="utf-8") as fh:
            json.dump(result, fh, separators=(",", ":"))


if __name__ == "__main__":
    main()
