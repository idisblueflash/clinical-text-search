---
reviewed: No
reviewed_by:
---

# 2026-07-23 — mtsamples-ner-v1 dataset + stratified sampler  (commit 41eb9b9)

## Scope decisions

- **CLI-driven, no UI yet.** UI work is deferred; we drive the pipeline from
  scripts and (for the baseline) from Claude directly. Rationale: prove the
  hard, domain-specific part (clean data + comparable NER) before spending
  effort on interface.
- **Claude is the baseline (PoC) NER model.** Its output must be saved in a
  model-agnostic format so GPT / local models can be compared later against the
  *identical* input bytes. Other models are OUT OF SCOPE for now — only the
  format has to accommodate them.

## Corpus: MTSamples (not MIMIC)

- Used `mtsamples.csv` (4,999 de-identified transcribed notes) from the
  companion repo `semantic-annotation-of-clinical-text`.
- **MIMIC-IV demo deliberately excluded**: restricted license (must never be
  committed) and it is mostly structured tables, not free-text narratives.

## Cleaning (before sampling): universe 4,922 of 4,999

- **Strip appended keyword tails (3,473 notes).** Most MTSamples notes have the
  original `keywords` column glued onto the end of the narrative with no
  separator — a lowercase comma-list. It is metadata, not clinical prose;
  leaving it in would inflate and trivialize NER (models would "find" entities
  in a tag dump). WHY it matters enough to fix carefully: two stripper bugs were
  found and fixed —
    1. tails ending in a trailing comma left an empty last token that halted the
       strip (was missing ~2,374 notes);
    2. a stub note (0068) whose narrative was basically empty + a keyword run
       broken by a >6-word phrase (0053) slipped through — fixed by raising the
       word cap to 10 (uppercase/period guards already exclude real prose) and
       dropping the over-cautious 40%-of-note safety guard.
  Residual keyword tails after fixes: ~103 corpus-wide (~2%), **0 in the 80.**
- **Drop empty/`nan` and sub-100-char stubs** (keyword-dominated notes strip
  down to near-nothing and are then removed by the min-length floor).

## Stratification: two axes, CLEF marginal-matching

Follows the project notes `stratified-sampling-balance-two-axes` /
`-guard-both-counters` (Roberts 2008): set target counts per group first
(marginals), draw at random, guard BOTH axis counters on every draw.

- **Axis 1 = specialty (given), thresholded at ≥2%.** 12 specialties clear 2%
  and are their own stratum; the 28 rarer ones pool into "Other" → 13 buckets,
  none empty. WHY 2%: with 40 raw specialties and heavy imbalance (Surgery 22%
  vs Hospice 0.1%), pure proportional allocation zeroes out ~13–19 specialties
  at practical N. Thresholding mirrors CLEF's own rare-category filter
  (`diagnosis-frequency-filter-five-percent`, which used 5%).
- **Axis 2 = note-type (derived).** 7 types via section-header rules
  (`header-rules-v1`), floor 1 so Pathology/Autopsy (0.5%) survives. WHY
  note-type over the `split` column: note-type carries different information
  from specialty (crosstab confirmed it cross-cuts, e.g. Radiology splits
  report/other; Surgery is mostly operative but not entirely) and genuinely
  exercises the two-axis method. `split` is carried in the manifest but is NOT
  an axis.
- **Draw order = rarity-first.** Shuffle (seeded) then stable-sort by global
  rarity, so scarce combos claim shared-bucket slots before common ones exhaust
  them. WHY: a shuffle-only single pass stalled at Pathology/Autopsy 0/1 (its
  only note sits in the shared "Other" bucket, which filled first) — exactly the
  endgame stall the guard-both-counters note predicts. Rarity-first fixed it;
  all marginals now hit exactly, 80/80.
- **N = 80**, seed = 20260723, reproducible.

## Entity schema: CLEF (Roberts 2008), 6 entities + 3 modifiers

- Entities: Condition, Intervention, Investigation, Result, Drug_or_device,
  Locus. Modifiers: Negation, Laterality, Sub_location. See `SCHEMA.md`.
- WHY include Negation from the start: negation is the central theme of the
  companion notebook and of clinical meaning ("denies chest pain").

## Format: frozen input vs. sibling runs

- `docs/NNNN.txt` = cleaned narrative, the **char-offset ground truth**;
  `manifest.jsonl` SHA-pins each note's bytes.
- Model predictions live OUTSIDE the dataset dir: `runs/<model>/` (identical
  shape per model). WHY: any later model annotates the same frozen bytes, so
  agreement/F1 between two runs is mechanical. Dataset committed to git for
  reproducibility.
