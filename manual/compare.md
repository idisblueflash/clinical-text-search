---
reviewed: No
reviewed_by:
---

# `compare.py` — how to compare two (or more) runs

`scripts/compare.py` scores how well runs agree, span by span, over the **same
frozen dataset**. The plan behind it (why F1, why a separate modifier pass, all
the checks) is [`specs/compare.md`](../specs/compare.md); this page is the how-to.

## What it does

Takes two or more `runs/<model>/` dirs and reports **span-level F1** between each
pair. One tool, three uses (same math each time):

- **self-consistency** — the same model repeated (`m-r1` vs `m-r2` vs `m-r3`): is
  it steady? This is the ceiling for every other score.
- **run-vs-run agreement** — different models (Sonnet vs the Opus reference): do
  they agree?
- **accuracy vs gold** — a run vs a human gold set, once one exists (same code).

Before scoring it **checks and stops on bad data**: every run must annotate the
frozen bytes (sha256), each located span must satisfy `doc[start:end] == text`,
every label must be in `SCHEMA.md`, and all runs must share one `schema_ver`.
Docs a run failed or is missing are reported as a **gap**, never scored as zero.

## Usage

```
uv run python scripts/compare.py RUN RUN [RUN ...] [options]
```

You need at least two runs. Use three or more of the *same* model for a
self-consistency score.

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `--dataset DIR` | `datasets/mtsamples-ner-v1` | The frozen dataset, used for the checks. |
| `--match exact\|relaxed` | `exact` | `exact` = same `[start,end)` **and** label. `relaxed` = spans **overlap** + same label. |
| `--by-type` | (always on) | Print the per-label block. It prints anyway; per-label is always in `--json`. |
| `--json OUT.json` | — | Write the full result object (all pairs, per-label, modifiers). |

Run it **twice — once `exact`, once `relaxed`** — and read the gap between them:
a big jump means the models pick the *same* entities but draw *different
boundaries*; both low means they disagree on the labels themselves.

## Examples (real output)

### Sonnet vs the Opus silver standard — exact match

```
$ uv run python scripts/compare.py runs/opus-agent-r1 runs/anthropic-claude-sonnet-5
dataset: mtsamples-ner-v1   match: exact   runs: opus-agent-r1, anthropic-claude-sonnet-5
  WARN temperature differs across runs: opus-agent-r1=None, anthropic-claude-sonnet-5=0.0
  WARN prompt_ver differs across runs: opus-agent-r1=None, anthropic-claude-sonnet-5='ner-v1'
  WARN reasoning_effort differs across runs: opus-agent-r1=None, anthropic-claude-sonnet-5='none'
  WARN model differs across runs: opus-agent-r1='claude-opus-4-8', anthropic-claude-sonnet-5='anthropic/claude-sonnet-5'
  opus-agent-r1: 80 docs scored  (1 unlocated spans dropped)
  anthropic-claude-sonnet-5: 80 docs scored  (27 unlocated spans dropped)

ENTITY F1 (exact match)
  pair                                           micro   macro    prec     rec  docs
  opus-agent-r1 | anthropic-claude-sonnet-5      0.535   0.539   0.565   0.509    80

by entity type (mean pairwise micro-F1)
  Condition          0.532
  Intervention       0.410
  Investigation      0.589
  Result             0.281
  Drug_or_device     0.678
  Locus              0.619

modifiers (separate pass): 0.165
  Negation           0.260
  Laterality         0.080
  Sub_location       0.044
```

### Same pair — relaxed match

```
$ uv run python scripts/compare.py runs/opus-agent-r1 runs/anthropic-claude-sonnet-5 --match relaxed
...
ENTITY F1 (relaxed match)
  pair                                           micro   macro    prec     rec  docs
  opus-agent-r1 | anthropic-claude-sonnet-5      0.735   0.733   0.776   0.698    80

by entity type (mean pairwise micro-F1)
  Condition          0.821
  Intervention       0.654
  Investigation      0.693
  Result             0.523
  Drug_or_device     0.821
  Locus              0.748

modifiers (separate pass): 0.268
  Negation           0.374
  Laterality         0.184
  Sub_location       0.088
```

**How to read it:** exact 0.535 → relaxed 0.735. The two models mostly agree on
*what* is an entity and *which* label, but draw *different boundaries* (Condition
and Drug_or_device jump to 0.82 relaxed). That boundary gap is the signal — it
points at the span-boundary rules the guideline still underspecifies. `Result`
and the modifiers are the weakest, exact or relaxed.

**Reminder:** `opus-agent-r1` is a *silver* standard, not gold, and Sonnet is the
same model family as Opus — same-family agreement reads high. So these numbers are
*agreement*, not *accuracy*.

## Output files

- **stdout** — the tables above. Nothing is written unless you pass `--json`.
- **`--json OUT.json`** — the full result object:

```json
{
  "dataset": "mtsamples-ner-v1",
  "match": "exact",
  "runs": ["opus-agent-r1", "anthropic-claude-sonnet-5"],
  "pairwise": {
    "opus-agent-r1|anthropic-claude-sonnet-5": {
      "micro_f1": 0.535, "macro_f1": 0.539,
      "precision": 0.565, "recall": 0.509,
      "docs_scored": 80, "gap": [],
      "spans": {"a": 5562, "b": 6182, "matched": 3144},
      "by_type": {"Condition": 0.532, "...": 0.0},
      "modifiers_micro_f1": 0.165,
      "modifiers_by_type": {"Negation": 0.260, "...": 0.0}
    }
  },
  "aggregate_f1": {"mean": 0.535, "min": 0.535, "max": 0.535, "stdev": 0.0},
  "aggregate_kind": "agreement",
  "by_type": {"Condition": {"mean_f1": 0.532}},
  "modifiers": {"mean_f1": 0.165, "by_type": {"Negation": {"mean_f1": 0.260}}}
}
```

With **three or more runs**, `pairwise` holds every `K(K-1)/2` pair and
`aggregate_f1` gives **mean ± spread** — the spread is the point of a
self-consistency run. `aggregate_kind` reads `self-consistency` when all runs are
the same model, else `agreement`.

## Gotchas

- **Run exact *and* relaxed.** One number hides whether a low score is a boundary
  problem or a label problem. The two side by side tell you which.
- **Unlocated spans are dropped, not matched.** A span the annotator emitted but
  the resolver could not place (`start/end = null`) has no offsets to compare, so
  it is excluded and counted in the header line. Usually a duplicate mention.
- **`temp=0` self-consistency is meaningless.** Most models barely vary at
  `temp=0`, so self-F1 ≈ 1.0 measures nothing. For a real self-consistency score,
  make the `r1/r2/r3` runs at **production temperature** (see `specs/compare.md`).
  `compare.py` warns when temperature differs across the runs you give it.
- **The WARN lines are expected here.** Comparing Sonnet against the offline Opus
  reference, they differ in model/prompt/temperature — that is a cross-model
  comparison, so the warnings are informational. They matter when you *meant* the
  runs to be identical (self-consistency).
- **Modifiers are scored separately and read low.** A modifier only matches once
  its target entity matches, so modifier F1 sits below entity F1 by design. Read
  it as its own line, not folded into the entity total.
- **Failed / missing docs are a gap, not a zero.** If a run failed some docs,
  `compare.py` scores only the shared docs and prints the gap ids. Fix the run
  (e.g. re-annotate with a larger `--max-tokens`) rather than comparing on a
  thinned set.
```
