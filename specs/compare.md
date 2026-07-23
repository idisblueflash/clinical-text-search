# Spec: `compare.py` — run-vs-run agreement

**STATUS: SPEC — not built yet.** The plan for the evaluation tool. When it is
built, it gets a `manual/compare.md` page with real output; this file is the
"why/what" that page's "how" will point back to.

## Purpose

Measure how well two (or more) runs agree, span by span, over the **same frozen
dataset**. One tool, two uses — same code, different inputs:

- **Self-consistency** (the near-term goal): runs of the *same* model
  (`claude-opus-4-8-r1` vs `-r2` vs `-r3`). Answers *is the model steady?* This is
  the **ceiling** for every other score — a model can't match a gold set (or
  another model) better than it matches itself. Some local models are thought to
  be unsteady, so this is the driver for building it now.
- **Run-vs-run agreement**: different models (Claude vs GPT vs local). Answers *do
  the models agree?*

Both are the same operation: span-level F1 between two `predictions.jsonl` files.
Accuracy vs a gold set is the same operation again, once a gold set exists — so
this one tool is the core of all three (see the metric table in `devlog.md`).

## Why F1, not kappa

Span extraction has no fixed list of items and no countable "negative" class
(annotators *propose* different spans; the number of non-entities depends on
tokenization and has no fixed value). So chance-corrected agreement (Cohen/Fleiss
kappa) is not well-defined here. **Span-level F1 counts matched spans and is
symmetric, so it *is* the agreement measure.** (If you ever need one
chance-corrected number: Krippendorff's α over per-token BIO labels — deferred.)

## Inputs

```
python3 scripts/compare.py RUN [RUN ...] \
    [--dataset datasets/mtsamples-ner-v1] \
    [--match exact|relaxed] \
    [--by-type] \
    [--json OUT.json]
```

- `RUN` — a `runs/<model>/` dir (needs `predictions.jsonl` + `run.json`). Two or
  more; use ≥3 for a self-consistency score.
- `--dataset` — the frozen dataset, used for **checks** (default
  `datasets/mtsamples-ner-v1`).
- `--match` — how to match spans (see below); default `exact`.
- `--by-type` — also print per-label F1 (it prints anyway; the flag adds detail).
  Per-label is always in the JSON.
- `--json` — write the full result object; otherwise print the table only.

## Metric

For each **pair** of runs, over every `doc_id` they share:

1. Match entity spans between run A and run B using `--match`.
2. Count matches → **precision, recall, F1** (F1 is the reported agreement).
   Swapping which run is "gold" flips P and R but not F1.
3. Report two ways: **micro** (pool all spans across docs) and **macro** (average
   the per-doc F1). Report both — macro shows a few very bad docs that the micro
   average hides.
4. **Per label** (`Condition`, `Locus`, …). `Locus` and `Negation` (lots of
   boundary calls) will be far less steady than `Drug_or_device`; one overall
   number hides this.

For **more than 2 runs**: compute all `K(K-1)/2` pair F1s, and report **mean ±
spread** (min/max or stdev). The spread is the point — don't report only the mean.

### Match rules

- `exact` (main): same `[start, end)` **and** same `label`.
- `relaxed`: spans **overlap** + same `label`. Showing exact and relaxed side by
  side separates *boundary* disagreement (relaxed much higher than exact) from
  real *label* disagreement (both low).
- **Modifiers** (`Negation`, `Laterality`, `Sub_location`) are scored in a
  **separate pass**. Their `modifies` pointer is an index into that run's own
  entity list, so a modifier match only counts once its target entity matches — or
  the numbers mean nothing. Keep entity-F1 and modifier-F1 on separate lines; do
  not fold modifiers into the entity totals.

## Checks (fail loudly; never score bad data)

Before scoring, for every run:

1. **Same bytes** — each `doc_id` must match the dataset's pinned `text_sha256`.
   If a run annotated different bytes, its offsets can't be compared → **stop**,
   and name the doc.
2. **Offset sanity** — `entities[i].text == doc[start:end]` for the frozen
   `docs/<doc_id>.txt`. A mismatch → stop (the run is misaligned).
3. **Labels / schema** — every label must be in `SCHEMA.md`'s set; an unknown
   label → stop. If `run.json.schema_ver` differs between runs → **refuse**
   (agreement across schema versions has no meaning).
4. **Doc coverage** — if runs cover different `doc_id`s, score the ones they share
   and **report the gap** (count + ids); never treat a missing doc as a zero.

## Output

Printed: a small table — micro/macro F1 per pair, the K-run mean±spread, then the
per-label block. JSON (`--json`): the full object, e.g.

```json
{
  "dataset": "mtsamples-ner-v1",
  "match": "exact",
  "runs": ["claude-opus-4-8-r1", "claude-opus-4-8-r2", "claude-opus-4-8-r3"],
  "docs_scored": 80,
  "docs_gap": [],
  "pairwise_f1": {"r1|r2": 0.0, "r1|r3": 0.0, "r2|r3": 0.0},
  "self_consistency": {"mean_f1": 0.0, "min": 0.0, "max": 0.0, "stdev": 0.0},
  "by_type": {"Condition": {"mean_f1": 0.0}, "Locus": {"mean_f1": 0.0}},
  "modifiers": {"mean_f1": 0.0, "by_type": {"Negation": {"mean_f1": 0.0}}}
}
```

## Self-consistency: how to make the runs

The score only means something if the runs are the same except for sampling
noise. Each `run.json` **must** record — and `compare.py` should show — these,
held the same across `r1/r2/r3`:

- `model`, `prompt_ver`, `schema_ver`, `dataset` — the same across runs.
- **`temperature` / `top_p` / `seed`** — the trap. At `temp=0` most models barely
  vary, so self-F1 ≈ 1.0 and you learn nothing; run at the **real** temperature so
  the measured noise is the noise the pipeline will actually see. If these differ
  across runs, `compare.py` should **warn** — you'd be measuring the config, not
  the model.
- `K = 3` runs is the default first pass; more if the spread is wide.

## Out of scope for v1 of the tool

- Chance-corrected α (Krippendorff over BIO) — F1 is enough to rank steadiness.
- Accuracy vs a human gold — no gold set exists yet; the same code applies once it
  does.
- Relation scoring — relations aren't annotated (`mtsamples-re-v1`, later).
