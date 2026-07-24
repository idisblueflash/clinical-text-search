---
reviewed: No
reviewed_by:
---

# Backlog — deferred / not done / passed to later

Next up (immediate):
- [ ] **Claude baseline annotation** → `runs/claude-opus-4-8/predictions.jsonl`
      + `run.json`. Plan: 5-doc pilot first (eyeball span quality + format),
      then scale to 80. Open question: entities-only vs entities+Negation for
      the pilot (recommendation: entities + Negation).

Known limitations to revisit:
- [ ] **`note_type` is heuristic, not gold.** `header-rules-v1` was not
      validated against hand labels; it is a sampling axis only. If it later
      matters as data, validate or hand-correct.
- [ ] **~103 residual keyword tails corpus-wide (~2%).** None in the current 80,
      but the stripper is not perfect (tails with uppercase abbreviations like
      "CT"/"GERD" break the all-lowercase rule). Acceptable for a baseline.
- [ ] **Boundary rules in SCHEMA.md may need refinement** after seeing real
      annotation disagreements in the pilot.

Deliberately out of scope for this phase:
- [ ] **CLEF relations** (has_finding, has_indication, …) — relation extraction
      is a separate task; plan a `mtsamples-re-v1` after NER is stable.
- [ ] **Pure random-with-retries draw** was NOT chosen; rarity-first was, to
      guarantee the rarest marginal fills. If strict uniform randomness is later
      required, swap `draw()` (documented tradeoff — slower, can fail to
      converge on the scarcest cell).
- [ ] **GPT / local model runs** — format supports them; runs themselves later.
- [ ] **Evaluation harness** (`compare.py`: inter-run agreement / F1 against a
      gold set) — not written yet.
- [ ] **Gold standard + inter-annotator agreement** — later; the whole point of
      the frozen format is to accumulate one over time.

Downstream prototype stages (the query→narratives thread), not started:
- [ ] Query understanding (NL → concepts, negation, normalization)
- [ ] Concept normalization / UMLS codes (synonym matching)
- [ ] Retrieval + result presentation (highlighted evidence)
- [ ] UI (explicitly deferred — CLI-only for now)
- [ ] MIMIC-IV demo data — unused so far.
