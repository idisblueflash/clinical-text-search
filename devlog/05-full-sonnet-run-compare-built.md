---
reviewed: No
reviewed_by:
---

# 2026-07-23 — full Sonnet run + compare.py built; first agreement vs silver

## Decision: build compare.py now — the silver standard is inert without it

- A reference set has zero value until something can be scored against it. compare.py
  (specced in specs/compare.md) is the linchpin: it turns runs/opus-agent-r1/ from a
  stored artifact into a measuring instrument. Built it per the spec.
- Same operation serves all three uses (self-consistency / run-vs-run / accuracy-vs-gold):
  span-level F1 between two predictions.jsonl. Greedy one-to-one span matching (sorted
  by offset, deterministic). exact = same [start,end)+label; relaxed = overlap+label.
- Checks fail LOUD before scoring (never score bad data): sha256 == manifest, offset
  sanity doc[start:end]==text, labels in SCHEMA, one shared schema_ver (else refuse).
  Failed/missing docs => reported as a GAP, never scored as a zero (would fake-deflate).
- Modifiers scored in a SEPARATE pass: a modifier match counts only once its target
  entity is itself a matched pair across the runs (its `modifies` is a run-local index).
  Kept off the entity line by design — folding them in would corrupt the entity number.
- Unlocated spans (start/end null) are DROPPED from scoring + counted in the header:
  no offsets to compare, usually a duplicate mention. Config-drift WARN (temperature/
  prompt_ver/reasoning/model) so a self-consistency run can't silently measure config.

## Decision: --max-tokens 4000 is too small; the FULL run needs 12000

- First full Sonnet run (max_tokens=4000, temp 0, reasoning off) FAILED 14/80 docs, all
  the same signature: "Expecting ',' delimiter" at ~char 9000 = JSON truncated mid-array
  at the token cap. The failures were the LARGE, entity-dense notes (reference had up to
  221 spans on one) — exactly the docs we most want compared. Dropping 17.5% would bias
  the score toward easy notes.
- Fix: re-ran ALL 80 at --max-tokens 12000 (fits ~400 spans). Chose re-run-all over
  splicing the 14 back in: one coherent run.json (one config/date), and at temp 0 the
  66 good docs reproduce identically. Result: 0 failed, 27 unlocated (dup mentions),
  6926/6953 spans offset-verified, $2.18, ~23 min. LESSON: entity-dense extraction needs
  a generous output budget; the pilot's 3 small docs hid this.

## RESULT: first agreement — Sonnet vs the Opus silver (opus-agent-r1)

- Entity F1 = 0.535 exact / 0.735 relaxed (micro; macro ~ same). The 0.20 exact->relaxed
  gap = the models AGREE on what/which-label but DRAW DIFFERENT BOUNDARIES. Per type
  (relaxed): Condition 0.82, Drug_or_device 0.82, Locus 0.75; weakest Result 0.28 exact /
  0.52 relaxed. Modifiers 0.165 exact / 0.268 relaxed (Negation best, Laterality/
  Sub_location near 0). JSON saved at runs/anthropic-claude-sonnet-5/compare_vs_opus-agent-r1.json.
- INTERPRETATION: the boundary gap is the disagreement-mining payoff — it lands on the
  exact guideline gaps the parallel-agent entry already flagged (#1 Laterality-on-Condition,
  #3 dose-as-Result, #4 Condition+site splitting). This is signal to HARDEN the guideline,
  not just a score. CAVEAT (unchanged): silver != gold, and Sonnet is Opus's own family, so
  correlated bias reads this HIGH — 0.735 is agreement, not accuracy.

DEFERRED: (a) self-consistency Sonnet x3 at PRODUCTION temperature (temp 0 => self-F1 ~ 1.0,
measures nothing) to pin the reliability ceiling; (b) a CROSS-FAMILY candidate (e.g. GPT) to
cut same-family bias; (c) human-anchor a subset so numbers read as accuracy; (d) act on the
guideline gaps the boundary disagreement localizes.
