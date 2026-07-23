---
reviewed: No
reviewed_by:
---

# Annotation Guideline — Clinical Narrative NER (CLEF scheme)

How to mark named entities in a clinical note, for **every annotator — human or
LLM** — so different annotators give matching results. The labels and their exact
definitions are in
[`datasets/mtsamples-ner-v1/SCHEMA.md`](datasets/mtsamples-ner-v1/SCHEMA.md).
**This file is the *how*** — the steps, the judgment calls, and worked examples.
Both come from the CLEF corpus (Roberts et al. 2008); the paper card is
`semantic-annotation-of-clinical-text/papers/raw/roberts-2008-clef-corpus.md`.

> The machine version of these rules is the `SYSTEM_PROMPT` in
> `scripts/annotate.py`. If you change the rules here, bump that script's
> `PROMPT_VER` — runs made before and after the change are not comparable.
> Doing it the same way every time is what makes the data good (CLEF §4.1).

## 0. Scope

- You mark **spans**: 6 entity types + 3 modifiers. That is the whole task for v1.
- You do **not** mark relations (`has_finding`, `has_location`, …). Relations are
  a separate task (a future `mtsamples-re-v1`). When this guide names a relation,
  it is only to help you *pick a span* — never to mark the link.
- Mark **every mention.** If the same thing shows up three times, mark three
  spans. (CLEF links repeated mentions; we don't — each mention is its own span.)
- Mark **planned or hypothetical** items too ("consider radiotherapy" → mark
  *radiotherapy*). What matters is that the note says it, not that it happened.

## 1. The recipe — mark in this order

CLEF gives annotators a fixed order so they *miss less* (§4.1). Do the passes in
order; don't jump around:

1. **Read the whole note first.** Context sets the label (a "scan" that measures
   vs. an action that treats).
2. **Conditions** — every symptom, diagnosis, problem, injury.
3. **Loci** — every body location, structure, or substance.
4. **Investigations**, then their **Results** — tests, and what they found.
5. **Interventions** — actions that treat or change a condition.
6. **Drugs or devices**.
7. **Modifiers** — attach each to the entity it belongs to (Negation → Condition;
   Laterality → Locus/Intervention; Sub_location → Locus).
8. **Read again** — check each Condition for a negation you missed, and confirm
   each span is copied **word for word** and is the **longest** meaningful span.

## 2. Entity types — how to decide

Full definitions are in `SCHEMA.md`; here are the quick cues.

- **Condition** — a symptom, diagnosis, complication, problem, function/process,
  or injury. *Cue:* something the patient *has or feels*. (*melanoma*,
  *facial pain*, *fracture dislocation*, *secondaries*.)
- **Locus** — a body location, structure, substance, or physiologic function;
  usually *where* a Condition is. (*right groin*, *lymph node*, *C2*.)
- **Investigation vs. Intervention** — the call people get wrong most. Ask:
  **does the action *measure/study* the condition, or *change/treat* it?**
  - measures, has a finding → **Investigation** (*biopsy*, *PET scan*, *CT scan*).
  - changes or treats, usually no finding → **Intervention** (*groin dissection*,
    *radiotherapy*, *ORIF*).
- **Result** — the number or word that is the **finding of an Investigation**, and
  is *not itself a Condition*. (*normal*, *80mg*, *12 x 5.2 x 4.6 cm*.) If the
  finding is a disease, it is a **Condition**, not a Result (a biopsy that *finds*
  *melanoma* → Condition).
- **Drug_or_device** — usually a drug; sometimes a device (sutures, drains).
  (*co-codamol*, *DTIC*, *Hemovac drain*.)

## 3. Modifiers — mark the signal word, attach to one entity

A modifier is its **own span** (the signal word). It points at the one entity it
belongs to. In a run's output, `modifies` is that entity's index (`i`).

| Modifier | Attaches to | Signal examples |
| --- | --- | --- |
| `Negation` | a **Condition** | *no evidence*, *denies*, *without*, *ruled out* |
| `Laterality` | a **Locus** or **Intervention** | *right*, *left*, *bilateral* |
| `Sub_location` | a **Locus** | *extra*, *upper*, *lower*, *proximal* |

- Mark the **signal only**, not the whole phrase: in *"no evidence of
  secondaries"*, the Negation span is *no evidence*; *secondaries* is the
  Condition it belongs to.
- A Laterality/Sub_location can sit right before the Locus it belongs to
  (*right* → *second toe*).

## 4. Span and boundary rules

- **Word for word.** A span is an exact substring of the note — same words, same
  case, nothing added or trimmed. (Later, offsets are found by *searching for your
  span text in the frozen note*. A reworded span can't be found, so it is lost.)
- **Longest meaningful span.** Mark the biggest unit that makes clinical sense:
  *fracture dislocation* as one Condition, not *fracture* + *dislocation*.
- **No overlap between entity types.** One character belongs to at most one entity
  span. A modifier can sit *next to* its entity but must not overlap it.
- **Measurements** that belong to an Investigation are **Result** (*"12 x 5 cm"*).

## 5. Hard cases and conventions

These are the calls that come up again and again. Make them the same way each time.

- **"myocardial infarction"** → **one Condition**. Do *not* split it into
  Condition + Locus. (CLEF flags this exact case; we always make it one span.)
- **"groin dissection"** → **two spans**: *groin* (Locus) + *dissection*
  (Intervention). A procedure named by its site is site-Locus + action-entity,
  not one blob. Same for *"lymph node biopsy"* → *lymph node* (Locus) + *biopsy*
  (Investigation), and *"facial pain"* → *facial* (Locus) + *pain* (Condition).
- **Negation reach.** The Negation belongs to the Condition it denies, even with
  words in between (*"no evidence of extra pelvic secondaries"* → Negation *no
  evidence* belongs to Condition *secondaries*).
- **A finding that is a disease is a Condition, not a Result** (see §2 Result).
- **Lists** ("pain and swelling") → mark each item as its own Condition span.
- **Don't mark section headers or template text** (like a bare "DIAGNOSIS:"
  label) — mark the clinical content, not the form.

## 6. Full worked example

The standard CLEF passage (Roberts 2008, Tables 2–3), annotated. Relations are
shown *only to help you understand* — they are **not** part of v1 output.

> This patient has had a **lymph node** *biopsy* which shows **melanoma** in his
> *right* **groin**. It is clearly **secondaries** from the **melanoma** on his
> *right* **second toe**. Although his **PET scan** is **normal** he does need a
> **groin** *dissection*. We agreed to treat with **DTIC**, and then consider
> **radiotherapy**. We will perform a **CT scan** to look at the *left* **pelvic
> side wall**. There was *no evidence* of *extra* **pelvic secondaries**. Her
> **facial** **pain** was initially relieved by **co-codamol**.

| Span (word for word) | Label | modifies |
| --- | --- | --- |
| lymph node | Locus | |
| biopsy | Investigation | |
| melanoma | Condition | |
| right | Laterality | groin |
| groin | Locus | |
| secondaries | Condition | |
| melanoma | Condition | |
| right | Laterality | second toe |
| second toe | Locus | |
| PET scan | Investigation | |
| normal | Result | |
| groin | Locus | |
| dissection | Intervention | |
| DTIC | Drug_or_device | |
| radiotherapy | Intervention | |
| CT scan | Investigation | |
| left | Laterality | pelvic side wall |
| pelvic side wall | Locus | |
| no evidence | Negation | pelvic secondaries |
| extra | Sub_location | pelvic secondaries |
| pelvic secondaries | Condition | |
| facial | Locus | |
| pain | Condition | |
| co-codamol | Drug_or_device | |

*(Relations, for context only, not marked: biopsy `has_finding` melanoma;
melanoma `has_location` groin; PET scan `has_finding` normal; dissection
`has_target` groin; co-codamol `has_indication` pain.)*

## 7. Notes for LLM annotators

- **Copy span text word for word** (§4). This is a hard rule: offsets are found by
  searching for your text in the frozen note.
- **Output JSON only** — no prose, no code fence. Use the exact shape in
  `SCHEMA.md` / the `annotate.py` prompt: `{"entities": [{"text","label",
  "modifies?"}]}`, where `modifies` = the exact text of the entity you point at.
- **Don't invent spans**, and don't "clean up" the text (no expanding short forms,
  no fixing typos) — mark what is written.
- **Stay steady for scoring.** Run at the temperature the pipeline will really
  use. We measure how consistent a model is across repeats (`specs/compare.md`).

## 8. Where annotators disagree — slow down there

CLEF's agreement scores on narratives (strict IAA, Table 6) show which labels are
hard, so you know where to take care:

- **Easy / high agreement:** Laterality (95%), Drug_or_device (84%), Condition
  (81%), Locus (78%). These rarely cause a dispute.
- **Hard / low agreement — go slow:** Sub_location (63%), Intervention (64%),
  Negation (67%), Result (69%). Most of the trouble is the
  Investigation-vs-Intervention call (§2) and how far a negation reaches (§5).

## Source and versioning

CLEF scheme — Roberts et al. (2008), "Semantic Annotation of Clinical Text: The
CLEF Corpus", Tables 2–3 and §4.1. This guideline goes with `SCHEMA.md` (the
labels) and is distilled into `annotate.py`'s prompt (`PROMPT_VER`). Update both
together after you see real disagreements in a pilot.
