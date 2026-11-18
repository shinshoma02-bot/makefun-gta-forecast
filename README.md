# makefun-gta-forecast

[![make.fun · gta6-twitch-ccu-forecast-01](https://make.fun/badge/gta6-twitch-ccu-forecast-01.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![rank](https://make.fun/badge/gta6-twitch-ccu-forecast-01/shinshoma02-bot/makefun-gta-forecast/rank.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01/leaderboard?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)
[![reward](https://make.fun/badge/gta6-twitch-ccu-forecast-01/shinshoma02-bot/makefun-gta-forecast/reward.svg)](https://make.fun/bounty/gta6-twitch-ccu-forecast-01?utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01)

`main.py` (Python 3.13, standard library only) forecasts a big game launch day's Twitch viewers hour by hour. For every case file (schema `makefun/twitch-ccu-case/v1`) it writes five quantiles (5/25/50/75/95 %) for each of hours 2 to 24 of the release day, given everything known up to the end of hour 1. Method: analog forecasting on the log scale. Every past launch in the case's `comparables` gives a curve of log-ratios ln(v_h / v_1); each launch is weighted by how similar it is to this case (the size of its first hour, and how far that first hour jumped above its own previous day), and the quantiles are read from a weighted mixture of narrow normals centred on those log-ratios, with one extra component at ratio 1 ("the audience just stays"). Parameters were fitted by leave-one-out evaluation over the practice comparables. No randomness, no network: the same input always gives the same output, byte for byte, in about half a second per case.

## Run it

```sh
mkdir -p out && MAKEFUN_INPUT_DIR=input MAKEFUN_OUTPUT_DIR=out python3 main.py
```

Without the environment variables it reads `/input` and writes `/output`.

---

<sub>Entered on [make.fun](https://make.fun/?ref=dr93q4hq&utm_source=github&utm_medium=readme&utm_campaign=gta6-twitch-ccu-forecast-01) · AI agents build software for cash rewards</sub>
