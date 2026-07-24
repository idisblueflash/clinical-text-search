---
reviewed: Yes
reviewed_by: Flash Hu
---

# Self-consistency — each model against itself

How much a model agrees with **itself** when you run it again on the same 80 docs
with the **same setup and temperature**. This is the *vs-itself* report. For how
well a model matches the Opus silver, see [`COMPARISON.md`](COMPARISON.md).

Why it matters: self-consistency is a rough **ceiling**. A model can't agree with
a silver reference much better than it agrees with itself. It also splits a low
cross-model score into two causes:

- **Low self-consistency** → the model is *noisy*; more runs (or lower
  temperature) would help.
- **High self-consistency but low vs-silver** → the model is *stably wrong*;
  it makes the same systematic choices Opus doesn't. More runs will not help.

You need **≥2 runs** of the same model/setup for a pairwise number, and **≥3**
for a spread (min/max/stdev). Scores are micro-averaged over all spans, in both
match modes (see `COMPARISON.md` for what exact vs relaxed mean).

Rebuild, e.g. for gemma4:

```
uv run python scripts/compare.py runs/gemma4-e2b-r1 runs/gemma4-e2b-r2 runs/gemma4-e2b-r3 --match exact
uv run python scripts/compare.py runs/gemma4-e2b-r1 runs/gemma4-e2b-r2 runs/gemma4-e2b-r3 --match relaxed
```

## gemma4:e2b — local (Ollama), 3 runs @ temp 0.7

Runs `gemma4-e2b-r1`, `r2`, `r3`. Machine version:
`runs/gemma4-e2b-r1/self_consistency.json`.

| Match | Mean F1 | Min | Max | Stdev |
|---|---|---|---|---|
| Exact | 0.732 | 0.710 | 0.755 | 0.023 |
| Relaxed | 0.757 | 0.735 | 0.784 | 0.025 |

Pairwise exact F1: r1–r2 = 0.730, r1–r3 = 0.755, r2–r3 = 0.710.

Per-type (exact, mean over the 3 pairs): Intervention 0.80 and Locus 0.76 are the
steadiest; **Result 0.63** is the shakiest entity, and among modifiers **Laterality
0.21** is by far the least stable (Negation and Sub_location are 1.0, but on very
few spans).

**Read:** gemma4 is fairly self-consistent (~0.73) but agrees with Opus at only
0.16 ([`COMPARISON.md`](COMPARISON.md)). It is **stably wrong, not noisy** — the
same systematic disagreement every run.

## Models with only one run (no self-consistency yet)

Self-consistency needs the same model run ≥2 times. These have a single run, so
there is no number to report:

| Model | Runs so far | Status |
|---|---|---|
| Sonnet 5 — agent path | `sonnet-agent-r1` (+ `r2` partial) | **Pending** — `r2` batch agents hit the session limit mid-run; finish it to get Sonnet's ceiling next to its 0.736 vs-silver. |
| Qwen2.5 7B-Instruct | `qwen2-5-7b-instruct` | single run |
| Qwen3 1.7B | `qwen-qwen3-1-7b` | single run |
| Opus (silver) | `opus-agent-r1` | single run — this is the reference itself |

To add a model's self-consistency: run it ≥2 more times with the same
`--temperature` and settings, then `compare.py` the runs and add a section here.
