#!/usr/bin/env python3
"""GTA VI launch-day Twitch viewers forecaster (make.fun bounty).

Reads /input/<id>.in (or $MAKEFUN_INPUT_DIR), writes /output/<id>.out (or
$MAKEFUN_OUTPUT_DIR). Method: analog forecasting on the log scale. For every
comparable past launch we take the log-ratio of each later hour to its first
hour, weight launches by how similar they are to the case (size of hour 1 and
how much hour 1 jumped over the previous day), and read the quantiles from a
weighted mixture of normals centred on those log-ratios.
"""
import datetime as dt
import glob
import json
import math
import os

LEVELS = [0.05, 0.25, 0.5, 0.75, 0.95]
# tuned on leave-one-out over the comparables (see tune.py)
PARAMS = dict(bw_size=1.0, bw_jump=1.0, sd0=0.15, sd_slope=0.03,
              w_persist=0.5, min_h1=5000.0, flag_w=1.0, size_floor=0.0)


def parse(s):
    return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)


def ndtr(x):
    return 0.5 * math.erfc(-x / math.sqrt(2.0))


def mix_quantile(centres, weights, sd, tau):
    tw = sum(weights)
    lo = min(centres) - 6 * sd - 1.0
    hi = max(centres) + 6 * sd + 1.0
    for _ in range(80):
        mid = 0.5 * (lo + hi)
        c = sum(w * ndtr((mid - m) / sd) for m, w in zip(centres, weights)) / tw
        if c < tau:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def analog_curves(case):
    """(name, flagged, h1, jump, ratios{hour: log ratio}) for each usable comparable."""
    ds = parse(case["day_start"])
    out = []
    for c in case["comparables"]:
        if c["name"].startswith("Grand Theft Auto VI category"):
            continue
        m = {parse(h["from"]): h["viewers"] for h in c["hourly"]}
        v = [m.get(ds_c + dt.timedelta(hours=i)) for ds_c in [parse(c["day_start"])] for i in range(-24, 24)]
        day = v[24:]
        if not day[0] or day[0] <= 0:
            continue
        pre = [x for x in v[:24] if x is not None]
        jump = math.log(day[0] / (sum(pre) / len(pre))) if pre and sum(pre) > 0 else None
        ratios = {h + 1: math.log(max(day[h], 1) / day[0]) for h in range(1, 24) if day[h] is not None}
        if len(ratios) < 12:
            continue
        tier = c["unlock"] if isinstance(c.get("unlock"), str) else ""
        flagged = ("early-access-contaminated" in tier) or ("Tier: weak" in tier)
        out.append((c["name"], flagged, float(day[0]), jump, ratios))
    return out


def case_features(case):
    ds = parse(case["day_start"])
    h1 = float(max(case["known"][0]["viewers"], 1))
    pre = []
    for h in case.get("history_hourly") or []:
        t = parse(h["from"])
        if ds - dt.timedelta(hours=24) <= t < ds:
            pre.append(h["viewers"])
    jump = math.log(h1 / (sum(pre) / len(pre))) if pre and sum(pre) > 0 else None
    return h1, jump


def forecast_case(case, P=PARAMS, pool=None):
    h1, jump = case_features(case)
    pool = pool if pool is not None else analog_curves(case)
    rows = []
    for fr in case["forecast"]:
        h = fr["hour"]
        cen, wts = [0.0], [P["w_persist"]]
        for name, flagged, ch1, cjump, ratios in pool:
            if h not in ratios or ch1 < P["min_h1"]:
                continue
            w = math.exp(-0.5 * ((math.log(ch1) - math.log(h1)) / P["bw_size"]) ** 2)
            if jump is not None and cjump is not None:
                w *= math.exp(-0.5 * ((cjump - jump) / P["bw_jump"]) ** 2)
            if flagged:
                w *= P["flag_w"]
            if w > 1e-9:
                cen.append(ratios[h])
                wts.append(w)
        sd = P["sd0"] + P["sd_slope"] * math.sqrt(h - 1)
        qs = [h1 * math.exp(mix_quantile(cen, wts, sd, t)) for t in LEVELS]
        for i in range(1, 5):
            qs[i] = max(qs[i], qs[i - 1])
        rows.append({"hour": h, "q": [round(min(max(q, 1e-6), 1e9), 4) for q in qs]})
    return {"hours": rows}


def main():
    indir = os.environ.get("MAKEFUN_INPUT_DIR") or "/input"
    outdir = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    os.makedirs(outdir, exist_ok=True)
    for path in sorted(glob.glob(os.path.join(indir, "*.in"))):
        with open(path, encoding="utf-8") as f:
            case = json.load(f)
        res = forecast_case(case)
        cid = os.path.basename(path)[:-3]
        with open(os.path.join(outdir, cid + ".out"), "w", encoding="utf-8") as f:
            json.dump(res, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
