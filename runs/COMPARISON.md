---
reviewed: Yes
reviewed_by: Flash Hu
---

# Cross-model comparison — agreement with the Opus silver

How close **each model** lands to the **Opus silver reference**
(`runs/opus-agent-r1/`, role `reference`) on the frozen `mtsamples-ner-v1`
dataset (80 docs). This is the *cross-model* report — one model against another.
For how well a model agrees with **itself** across repeated runs, see
[`SELF_CONSISTENCY.md`](SELF_CONSISTENCY.md).

Scores are **micro-averaged** over all spans — the 6 entity types + 3 modifiers.
Two match modes (from `scripts/compare.py --match`):

- **Exact** — the span `[start, end)` and the label must both match.
- **Relaxed** — any character overlap counts, as long as the label matches. This
  forgives boundary differences (e.g. "left kidney" vs "kidney").

Rebuild the numbers with, for each run:

```
uv run python scripts/compare.py runs/opus-agent-r1 runs/<run> --match exact
uv run python scripts/compare.py runs/opus-agent-r1 runs/<run> --match relaxed
```

## Results

| Model — annotation path | Exact F1 | Exact P | Exact R | Relaxed F1 | Relaxed P | Relaxed R |
|---|---|---|---|---|---|---|
| **Sonnet 5 — agent path** (`sonnet-agent-r1`) | **0.736** | 0.802 | 0.680 | **0.811** | 0.883 | 0.749 |
| Qwen2.5 7B-Instruct — local (`qwen2-5-7b-instruct`) | 0.190 | 0.125 | 0.397 | 0.350 | 0.230 | 0.729 |
| gemma4:e2b — local, Ollama (`gemma4-e2b-r1`) | 0.163 | 0.094 | 0.583 | 0.228 | 0.132 | 0.817 |
| Qwen3 1.7B — local (`qwen-qwen3-1-7b`) | 0.075 | 0.041 | 0.431 | 0.131 | 0.072 | 0.751 |

## What the numbers say

- **Sonnet (agent path) is the only strong candidate** — 0.736 exact / 0.811
  relaxed. Its precision (0.80) shows it is not just marking a lot of spans and
  hoping; the spans it marks are mostly right.
- **Local models over-annotate.** They find a lot (relaxed recall 0.73–0.82) but
  mark far more spans than Opus did, so exact precision is only 0.04–0.13. High
  recall, low precision.
- **gemma4's low score is systematic, not noise.** It scores only 0.16 vs Opus,
  yet agrees with *itself* at ~0.73 (see [`SELF_CONSISTENCY.md`](SELF_CONSISTENCY.md)).
  So the gap is a real disagreement with the silver, not random variance — more
  runs will not close it.

## Notes

- gemma4 is shown as `r1`; runs `r2`/`r3` land within ~0.01, so the row is
  representative.
- The full Sonnet run over the plain OpenRouter API (`runs/anthropic-claude-sonnet-5/`)
  is left out of this table. It scored 0.535 exact — far below the *same* model on
  the agent path (0.736). That gap is the "annotation path dominates the model"
  finding; see `devlog.md`. The run stays in `runs/` as evidence.
