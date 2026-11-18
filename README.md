# makefun-gta-forecast

make.fun bounty: forecast GTA VI's launch-day Twitch viewers, hour by hour
(`gta6-twitch-ccu-forecast-01`).

## What it does
`main.py` (Python 3.13, stdlib only) reads each case `/input/<id>.in`
(schema `makefun/twitch-ccu-case/v1`) and writes `/output/<id>.out`:

```json
{"hours":[{"hour":2,"q":[q05,q25,q50,q75,q95]}, ... ,{"hour":24,"q":[...]}]}
```

23 rows (hours 2-24), five quantiles per hour (5/25/50/75/95 %), non-decreasing.

Method: analog forecasting on the log scale. From the case's `comparables` (past
big launches) it takes each launch's log-ratio of hour h to its hour 1, weights
launches by similarity (size of hour 1, jump of hour 1 over the previous 24 h),
and reads quantiles from a weighted mixture of normals (plus a "persistence"
component at ratio 1). Deterministic, no network, about 0.5 s per run.

## Run
```bash
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```
Without the env vars it reads `/input` and writes `/output` (grader default).

`tune.py <case.in> [grid]` is a dev-only leave-one-out check on the comparables
(baseline persistence loss 0.321 vs 0.256 for this model there).
