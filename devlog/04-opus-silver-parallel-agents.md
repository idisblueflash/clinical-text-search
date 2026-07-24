---
reviewed: No
reviewed_by:
---

# 2026-07-23 — Opus silver-standard reference via PARALLEL agent batches

## Decision: strong-model (Opus) reference = a SILVER standard, not gold

- Annotate the 80 with a strong model (Opus, via the Claude Code agent — NOT the
  OpenRouter API) to get a reference other/cheaper models are compared against.
- Naming matters: it is a SILVER standard (LLM reference), not gold (= human
  consensus). Agreement-with-Opus ≠ correctness. Biggest caveat: correlated bias,
  worst when candidate is SAME family (Opus->Sonnet reads high). Good for ranking,
  dev velocity, disagreement-mining, and as a draft for humans to correct.
  Hardening later: cross-family consensus + a small human-anchor set.
- Offline path (no API): agent emits VERBATIM text+label per doc; resolve_run.py
  computes offsets into the standard runs/<name>/ format. Built resolve_run.py +
  check_offsets.py + manual/agent-annotation.md for this.
- REASONING flips vs the OpenRouter extraction path: for a cheap candidate we run
  reasoning OFF (thinking burns the token budget → empty content); for a quality
  REFERENCE, thinking is fine (agent-native Opus) — quality over cost.

## Decision: chunk the docs across PARALLEL agents (not one long agent)

- Problem observed: a single agent doing all 80 ACCUMULATES context — every doc
  read + file written stays in-window. Two failures: (1) cost/latency grows per
  later doc; (2) CONTEXT DRIFT — doc 40 annotated in a noisier state than doc 1,
  so quality is non-uniform. First single-agent run was stopped at 40/80 for this.
- Fix: partition into ~10-doc batches, one COLD-START Opus agent per batch, run in
  PARALLEL. 80 docs -> 8 agents (0001-0010 … 0071-0080), identical spec, only the
  doc-id list differs. Bounded uniform context, parallel wall-clock, fault
  isolation. Merge is free: all write the same raw/, resolve_run reads all of it.
- Reconciled with the earlier "one annotator" guidance: consistency lives in the
  GUIDELINE + schema + prompt + same model, NOT in it being one process. Cold-start
  agents REMOVE the drift a single long run has, so chunked is typically MORE
  consistent. Residual risk = ambiguous-case divergence between agents, mitigated
  by explicit guideline conventions (and surfaces as signal to harden them). This
  is planned uniform partitioning, not ad-hoc "second agent wings the remainder".
- Chose option #2 (redo all 80 chunked; discarded the drift-contaminated 0001-0040)
  over #1 (keep 40 + chunk rest) for pristine uniform provenance.

## RESULT: opus-agent-r1 complete (80/80)

- 8 parallel batches all finished; merged raw/ = 80/80 valid JSON, no missing/extra.
- resolve_run.py: 80/80 resolved, 1 unlocated span (0020 'no evidence' Negation —
  duplicate emission, correct conservative behavior). check_offsets.py: RESULT OK,
  6215/6216 located & verified, 0 problems. run.json role=reference.
- Label dist: Locus 1754, Condition 1629, Drug_or_device 758, Intervention 517,
  Result 455, Investigation 449, Negation 307, Laterality 272, Sub_location 75.
  Spans/doc: min 6 (0067 therapeutic-rec note), max 221 (0034 IME), mean 78.
- The '0033 issue' an early agent saw was a transient mid-write read; 0033 clean.

## Guideline gaps surfaced by the parallel cold-start agents (HARDEN guideline.md)

The batches independently exposed where guideline.md / SCHEMA.md underspecify.
These are the adjudication items for a v2 guideline (ranked by how many agents hit
them / impact on span counts):

1. **Laterality on a side-bearing Condition** — 5 agents independently. Schema
   allows Laterality only on Locus/Intervention, so "right hemiparesis" / "left
   radiculopathy" lose the side (folded into one Condition). Need an explicit rule
   (allow Laterality→Condition? or split a Locus? or accept the loss). #1 priority.
2. **Annotation EXHAUSTIVENESS of normal/negated exam findings + vitals** — biggest
   driver of cross-batch span-count variance. Treatments seen: mark normal findings
   as Result ("intact","2+","within normal limits"); mark as negated Condition;
   or skip. Vitals as Investigation+Result vs skip. Guideline must rule on how
   exhaustively to annotate, not just labels.
3. **Drug dose as Result** — ~50/50 split. SCHEMA's own "80mg" example says Result,
   but the definition (finding of an Investigation) says no; agents split. Fix the
   schema example or add an explicit dose rule.
4. **Condition + site splitting** — every agent called it the fuzziest boundary
   (split "cervical stenosis"→Locus+Condition vs keep compound diagnoses whole).
   Guideline has the facial-pain example but needs more worked cases.
5. **Coordinated negation** ("denies A, B, C") — modifies points at ONE entity, so
   only the first conjunct gets negated. Real scope limitation of the span format.
6. **Uncertainty as Negation** — agents mapped "possible/probable/suspected/cannot
   be assessed" to Negation (per "negated OR uncertain"). Consistent but worth an
   explicit list.
7. Minor: scopes/instruments as Drug_or_device vs omit; Sub_location vs fused Locus
   ("lower back"); implanted grafts (homograft valve, Lap-Band) Locus vs device;
   family-history conditions skipped (patient-only).

DEFERRED: (a) revise guideline.md/SCHEMA.md per the above → would bump PROMPT_VER +
a new reference round; (b) this is a SILVER standard — human-correct a subset to
anchor it; (c) run a candidate (Sonnet full 80) + compare.py vs this reference.
