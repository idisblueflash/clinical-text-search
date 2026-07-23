# Spec: `compare.py` — run-vs-run agreement

**STATUS: SPEC — not built yet.** Design intent for the deferred evaluation
harness. When built, it gets a `manual/compare.md` page with real output; this
file is the "why/what" that page's "how" will point back to.

## Purpose

Compute span-level agreement between two (or more) prediction runs over the
**same frozen dataset**. One tool, two uses — same code, different inputs:

- **Self-consistency** (primary near-term goal): runs of the *same* model
  (`claude-opus-4-8-r1` vs `-r2` vs `-r3`). Answers *is the model stable?* — the
  **reliability ceiling** for everything downstream. This is the driver for
  building it now; some local models are suspected unstable.
- **Cross-model agreement**: different models (Claude vs GPT vs local). Answers
  *do models converge?*

Both are the identical operation: span-level F1 between two `predictions.jsonl`
files. Accuracy-vs-gold is the same op again once a gold set exists, so this tool
is the reusable core of all three (see the metric table in `devlog.md`).

## Why F1, not kappa

Span extraction has no fixed item set and no countable negative class (annotators
*propose* different spans; "number of non-entities" is tokenization-dependent and
unbounded), so chance-corrected agreement (Cohen/Fleiss kappa) is ill-defined
here. **Span-level F1 is symmetric for matched-span counting, so it *is* the
agreement measure.** (If a single chance-corrected number is ever needed:
Krippendorff's α over per-token BIO labels — deferred.)

## Inputs

```
python3 scripts/compare.py RUN [RUN ...] \
    [--dataset datasets/mtsamples-ner-v1] \
    [--match exact|relaxed] \
    [--by-type] \
    [--json OUT.json]
```

- `RUN` — a `runs/<model>/` dir (needs `predictions.jsonl` + `run.json`). Two or
  more; ≥3 expected for a self-consistency estimate.
- `--dataset` — frozen dataset dir, for **validation** (default
  `datasets/mtsamples-ner-v1`).
- `--match` — span-match criterion (see below); default `exact`.
- `--by-type` — also print per-entity-type F1 (default: print anyway; flag toggles
  verbosity). Per-type is not optional in the JSON.
- `--json` — write the full result object; else print table only.

## Metric

For each **pair** of runs, over every `doc_id` they share:

1. Match entity spans between run A and run B under `--match`.
2. Count matches → **precision, recall, F1** (F1 is the reported agreement).
   Treating A-as-gold vs B-as-gold flips P/R but not F1.
3. Aggregate two ways: **micro** (pool all spans across docs) and **macro**
   (mean of per-doc F1); report both — macro exposes a few catastrophic docs the
   micro average hides.
4. **Per entity type** (`Condition`, `Locus`, …) — boundary-heavy `Locus` and
   `Negation` will be far less stable than `Drug_or_device`; the overall number
   hides this.

For **K > 2** runs: compute all `K(K-1)/2` pairwise F1s, report **mean ± spread**
(min/max or stdev). The spread is the point — don't collapse to the mean alone.

### Match criteria

- `exact` (primary): identical `[start, end)` **and** identical `label`.
- `relaxed`: span **overlap** + identical `label`. Reporting exact vs relaxed
  side-by-side separates *boundary* disagreement (relaxed >> exact) from genuine
  *label* flips (both low).
- **Modifiers** (`Negation`, `Laterality`, `Sub_location`) are scored in a
  **separate pass**, because their `modifies` pointer is an index into that run's
  own entity list — only compare a modifier match once its target entity matched,
  or the numbers are meaningless. Keep entity-F1 and modifier-F1 as distinct
  lines; do not fold modifiers into the entity totals.

## Validation (fail loudly, don't silently score garbage)

Before scoring, for every run:

1. **Byte identity** — each `doc_id` must correspond to the dataset's pinned
   `text_sha256`. If a run annotated different bytes, its offsets are
   incomparable → **abort** with the offending `doc_id`.
2. **Offset sanity** — `entities[i].text == doc[start:end]` for the frozen
   `docs/<doc_id>.txt`. Mismatch → abort (misaligned run).
3. **Schema/label set** — labels must be within `SCHEMA.md`'s set. Unknown label
   → abort. If `run.json.schema_ver` differs between runs → **refuse** (agreement
   across schema versions is not meaningful).
4. **Doc coverage** — if runs cover different `doc_id` sets, score the
   intersection and **report the gap** (count + ids); never pad a missing doc as
   zero silently.

## Output

Printed: a compact table — overall micro/macro F1 per pair, the K-run mean±spread,
then the per-type block. JSON (`--json`): the full object, e.g.

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

## Self-consistency protocol (how the runs must be produced)

The number is only meaningful if the runs are identical except for sampling
noise. Each `run.json` **must** record — and `compare.py` should surface — the
following, held constant across `r1/r2/r3`:

- `model`, `prompt_ver`, `schema_ver`, `dataset` — identical across runs.
- **`temperature` / `top_p` / `seed`** — the trap. At `temp=0` most models are
  near-deterministic → self-F1 ≈ 1.0 measures nothing; run at the **production
  temperature** so the measured noise is the noise the pipeline will actually
  see. If these differ across runs, `compare.py` should **warn** — you'd be
  measuring config, not the model.
- `K = 3` runs is the default first pass; more if the spread is wide.

## Deliberately out of scope for v1 of the tool

- Chance-corrected α (Krippendorff over BIO) — F1 is enough to rank stability.
- Accuracy vs a human gold — no gold set exists yet; same code applies when it does.
- Relation scoring — relations aren't annotated (`mtsamples-re-v1`, later).
