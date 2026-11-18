#!/usr/bin/env python3
"""Leave-one-out evaluation of main.py on the comparables (dev tool, not the entry)."""
import itertools, json, math, os, sys, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import main as M

def targets(base_case):
    res = []
    for i, c in enumerate(base_case["comparables"]):
        if c["name"].startswith("Grand Theft Auto VI category"):
            continue
        ds = M.parse(c["day_start"])
        m = {M.parse(h["from"]): h for h in c["hourly"]}
        day = [m.get(ds + dt.timedelta(hours=k)) for k in range(24)]
        if day[0] is None or day[0]["viewers"] < 20000:   # GTA-like scale only
            continue
        if sum(x is not None for x in day) < 20:
            continue
        hist = [h for t, h in m.items() if t < ds + dt.timedelta(hours=1)]
        case = {"day_start": c["day_start"], "known": [{"viewers": day[0]["viewers"]}],
                "history_hourly": [{"from": h["from"], "viewers": h["viewers"]} for h in hist],
                "forecast": [{"hour": k + 1} for k in range(1, 24)],
                "comparables": [x for j, x in enumerate(base_case["comparables"]) if j != i]}
        res.append((c["name"], case, {k + 1: day[k]["viewers"] for k in range(1, 24) if day[k]}))
    return res

def loss(res, y):
    tot = n = 0
    for r in res["hours"]:
        if r["hour"] not in y: continue
        ly = math.log(max(y[r["hour"]], 1))
        for tau, q in zip(M.LEVELS, r["q"]):
            d = ly - math.log(q)
            tot += 2 * max(tau * d, (tau - 1) * d); n += 1
    return tot / n

def baseline(case):
    p = case["known"][0]["viewers"]; z = [-1.645, -0.674, 0, 0.674, 1.645]
    return {"hours": [{"hour": h, "q": [p * math.exp(zz * 0.15 * math.sqrt(h - 1)) for zz in z]} for h in range(2, 25)]}

def evaluate(T, P):
    ls = []
    for name, case, y in T:
        pool = M.analog_curves(case)
        ls.append(loss(M.forecast_case(case, P, pool), y))
    return sum(ls) / len(ls), ls

if __name__ == "__main__":
    base = json.load(open(sys.argv[1]))
    T = targets(base)
    print(len(T), "targets:", [t[0][:12] for t in T])
    print("baseline", sum(loss(baseline(c), y) for _, c, y in T) / len(T))
    print("current ", evaluate(T, M.PARAMS)[0])
    if len(sys.argv) > 2:
        best = None
        grid = dict(bw_size=[1.0, 1.5, 2.5], bw_jump=[1.0, 1.5, 3.0], sd0=[0.12, 0.2, 0.3],
                    sd_slope=[0.0, 0.03, 0.06], w_persist=[0.0, 0.5, 1.5], flag_w=[0.3, 0.6, 1.0])
        for vals in itertools.product(*grid.values()):
            P = dict(M.PARAMS); P.update(dict(zip(grid, vals)))
            l = evaluate(T, P)[0]
            if best is None or l < best[0]: best = (l, P); print(round(l, 4), dict(zip(grid, vals)), flush=True)
