# Running TerraQ

Satellite mineral prospecting for lithium and vanadium. Three commands.

```bash
bash setup.sh      # once, after cloning
bash start.sh      # launch
bash stop.sh       # shut down
```

Then open **http://localhost:3000** — `start.sh` prints the real URLs, so read them
rather than assuming the port.

---

## What you need

| | Version | Why |
|---|---|---|
| **Python** | **3.12 exactly** | `pennylane 0.38` pins `numpy<2`, which does not resolve on 3.13+ |
| **Node.js** | 18 or newer | Next.js 16 |
| Disk | ~3 GB | mostly PyTorch |
| Internet | yes | the engine streams Sentinel-2 imagery live |

Installing Python 3.12:

```bash
brew install python@3.12                      # macOS
sudo apt install python3.12 python3.12-venv   # Debian / Ubuntu
```

`setup.sh` checks for it and stops with instructions if it is missing.

**No API keys are required.** Basemaps, geology, search and the whole engine are
key-free. A key only turns on the AI summary — see [Optional](#optional-ai-features).

---

## Before a demo

```bash
bash setup.sh --prewarm
```

This runs all 7 preset locations and caches them, so clicking **Analyze Region**
returns instantly. Without it the first analysis of any area takes **1–3 minutes**
while it streams imagery from AWS.

Do this ahead of time, never during a demo — the engine runs one job at a time,
so a prewarm in progress blocks everything else.

---

## What you get

| URL | |
|---|---|
| `localhost:3000` | Landing page |
| `localhost:3000/explorer` | **Exploration console** — the main thing |
| `localhost:3000/dashboard` | Research dashboard, 6 tabs |
| `localhost:8765` | Engine API (and its own plain demo page) |

### Try this first

1. Open `/explorer`
2. Press **Analyze Region** (it opens on Silver Peak, Nevada — cached, instant)
3. The panel shows the lithium index at that point, 12 detected targets, and
   the geology
4. Press **Validation** in the header to see how the index scores against USGS
   records

Search accepts place names (`Clayton Valley`), pasted coordinates
(`34.08, 74.80` or `37°44'59"N 117°38'03"W`), and reported mineral sites
(`Katghora`, `Marlagalla`).

---

## Optional: AI features

The **Ask** panel and the AI summary need a language-model key. Everything else
works without one — the summary falls back to a deterministic template.

Edit `terraq/.env.local` (setup.sh creates it blank):

```
LLM_PROVIDER=groq
GROQ_API_KEY=your_key_here
GROQ_MODEL=openai/gpt-oss-120b
GROQ_FALLBACK_MODEL=openai/gpt-oss-20b
```

Restart with `bash stop.sh && bash start.sh`. Keys are read server-side only and
never reach the browser.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Python 3.12 not found` | Install it (above). 3.13 and 3.14 will not work. |
| `Run setup first` | `bash setup.sh` |
| Port 3000 or 8765 busy | `start.sh` picks the next free port and prints it. Force with `DASH_PORT=3005 ENGINE_PORT=8770 bash start.sh` |
| Analysis takes minutes | Normal for an uncached area — it is streaming satellite imagery. Prewarm beforehand. |
| "engine offline" badge | The Python engine stopped. Check `.logs/engine.log`. |
| Search returns nothing | OpenStreetMap rate-limits shared IPs. Known mineral sites and pasted coordinates still work. |
| Blank map | Check the browser console; the basemaps (NASA GIBS, EOX) need internet. |

Logs live in `.logs/dashboard.log` and `.logs/engine.log`.

---

## What you cannot run

**The quantum research pipeline does not run from this repo.** It needs the
Hyperion `.npy` data cubes and two preprocessing scripts
(`step1_convert_hyperion.py`, `step2_load_usgs_spectra.py`) that are not
included — the raw imagery is ~17 GB.

Its results are committed as figures and metrics in `outputs/summary/`, and the
code is in `src/quantum/`. The dashboard reads those committed numbers.

The live Explorer is **entirely classical** and does not depend on any of it.

---

## Regenerating the analysis (optional)

None of this is needed to run the app — the outputs are committed.

```bash
./.venv/bin/python product/benchmark_console.py      # score against USGS ground truth
./.venv/bin/python product/export_console_data.py    # refresh the console's data files
./.venv/bin/python product/build_gazetteer.py        # rebuild the mineral-site search index
./.venv/bin/python product/verify_percentiles.py     # independently re-check the displayed percentiles
./.venv/bin/python product/run_validation_aois.py    # re-run the validation areas (~10 engine runs)
./.venv/bin/python product/validation_stats.py       # recompute the validation statistics
./.venv/bin/python product/build_validation_card.py  # rebuild the validation figure and data
```

---

## Honest scope

This detects **surface mineral alteration**. It cannot see brine lithium
dissolved underground, buried deposits, or black-shale vanadium. Scores are
**relative rankings within a single scene**, not probabilities and not
comparable between scenes.

Validation covers Nevada. The India work is a spot check that found the method
unusable over vegetated ground. The Explorer tells you which applies wherever
you are looking.

It generates candidates worth investigating. It does not confirm deposits.
