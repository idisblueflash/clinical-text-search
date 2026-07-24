---
reviewed: No
reviewed_by:
---

# 2026-07-23 — self-consistency metric + compare.py spec  (spec only, not built)

## Decision: measure model self-consistency first, via compare.py

Before trusting any accuracy number, measure whether a model is *stable* across
repeated runs on the identical frozen bytes. Full design: `specs/compare.md`.

- **It's self-consistency (test-retest), NOT IAA.** IAA is between *different*
  annotators; same-model-repeated is intra-annotator / test-retest reliability.
  Three distinct metrics, one tool:
    * self-consistency   — model vs itself (r1/r2/r3) — *is it stable?*  ← now
    * cross-model agree   — Claude vs GPT vs local     — *do they converge?*
    * accuracy vs gold    — model vs human gold         — *is it right?*
  All three are the same operation: span-level F1 between two predictions files.
- **WHY first:** self-consistency is the RELIABILITY CEILING — a model can't
  agree with gold (or another model) more than it agrees with itself. Without it,
  a 0.75-vs-gold could be pure noise. It also splits error into random (unstable)
  vs systematic (wrong the same way every time). Driver: some local models are
  suspected inconsistent; this quantifies it instead of eyeballing.
- **Metric = pairwise span-level F1, NOT kappa.** Span extraction has no fixed
  item set and no countable negative class, so chance-corrected kappa is
  ill-defined. F1 is symmetric for matched-span counting, so it IS the agreement
  measure. K=3 runs → mean ± spread over the 3 pairs; per-entity-type breakdown
  (Locus/Negation less stable than Drug_or_device); exact + relaxed match to
  separate boundary disagreement from label flips. Modifiers scored in a separate
  pass (their `modifies` index is run-local).
- **THE TRAP (temperature).** The estimate is only meaningful if runs are
  identical except sampling noise. Fix + record temperature/top_p/seed in every
  run.json. At temp=0 most models are near-deterministic → self-F1 ≈ 1.0 measures
  nothing; run at PRODUCTION temperature so measured noise = pipeline's real
  noise. compare.py warns if these differ across runs.
- **Near-free given existing design.** runs/<model>/ already supports multiple
  runs (r1/r2/r3); compare.py is the deferred eval harness, now specced. N=80
  docs = hundreds of spans, ample for a stability estimate.

DEFERRED (unchanged): compare.py itself not yet built; Krippendorff α over BIO
and accuracy-vs-gold both out of scope until there's a reason / a gold set.
