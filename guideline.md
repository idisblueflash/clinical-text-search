# Annotation Guideline — Clinical Narrative NER (CLEF scheme)

How to annotate a clinical narrative with named entities, for **every annotator —
human or LLM** — so that different annotators produce comparable results. The
label set and formal definitions live in
[`datasets/mtsamples-ner-v1/SCHEMA.md`](datasets/mtsamples-ner-v1/SCHEMA.md);
**this file is the *how*** — the decision process, conventions, and worked
examples. Both are adopted from the CLEF corpus (Roberts et al. 2008); the paper
card is `semantic-annotation-of-clinical-text/papers/raw/roberts-2008-clef-corpus.md`.

> The machine version of this guideline is the `SYSTEM_PROMPT` in
> `scripts/annotate.py` — a distilled form of the rules below. If you change the
> rules here, bump that script's `PROMPT_VER` (runs across the change aren't
> comparable). Consistency is *the* determinant of gold-standard quality (CLEF §4.1).

## 0. Scope

- You mark **spans**: 6 entity types + 3 modifiers. That is the whole task for v1.
- You do **not** mark relations (`has_finding`, `has_location`, …). Relations are
  a separate task (a future `mtsamples-re-v1`). Where this guide mentions a
  relation, it is only to help you *decide a span*, never to annotate the link.
- Mark **every mention.** If the same real-world thing appears three times, mark
  three spans (CLEF links co-references; we don't — each mention is its own span).
- Annotate **planned / hypothetical** items too ("consider radiotherapy" → mark
  *radiotherapy*). Presence in the text is what matters, not whether it happened.

## 1. The recipe — annotate in this order

CLEF gives annotators a fixed recipe to *minimise errors of omission* (§4.1). Do
the passes in order; don't free-associate:

1. **Read the whole note first.** Context decides labels (a "scan" that measures
   vs. an action that treats).
2. **Conditions** — every symptom, diagnosis, problem, injury.
3. **Loci** — every anatomical location/structure/substance.
4. **Investigations**, then their **Results** — tests and what they found.
5. **Interventions** — actions that treat/change a condition.
6. **Drugs or devices**.
7. **Modifiers** — for each, attach it to the entity it qualifies (Negation →
   Condition; Laterality → Locus/Intervention; Sub_location → Locus).
8. **Re-read** — check every Condition for negation/uncertainty you missed, and
   confirm each span is copied **verbatim** and is the **maximal** span.

## 2. Entity types — how to decide

Full definitions in `SCHEMA.md`; here are the discriminating cues.

- **Condition** — a symptom, diagnosis, complication, problem, function/process,
  or injury. *Cue:* something the patient *has/experiences*. (*melanoma*,
  *facial pain*, *fracture dislocation*, *secondaries*.)
- **Locus** — an anatomical location/structure, body substance, or physiologic
  function; typically *where* a Condition is. (*right groin*, *lymph node*, *C2*.)
- **Investigation vs. Intervention** — the single most error-prone call. Ask:
  **does the action *measure/study* the condition, or *change/treat* it?**
  - *measures, has a finding* → **Investigation** (*biopsy*, *PET scan*, *CT scan*).
  - *changes/treats, usually no finding* → **Intervention** (*groin dissection*,
    *radiotherapy*, *ORIF*).
- **Result** — the numeric or qualitative **finding of an Investigation**, and
  *not itself a Condition*. (*normal*, *80mg*, *12 x 5.2 x 4.6 cm*.) If the finding
  is a disease, that's a **Condition**, not a Result (a biopsy *finding* of
  *melanoma* → Condition).
- **Drug_or_device** — usually a drug; sometimes a device (sutures, drains).
  (*co-codamol*, *DTIC*, *Hemovac drain*.)

## 3. Modifiers — mark the signal, attach to one entity

A modifier is its **own span** (the signal word), pointing at the single entity
it qualifies. In a run's output, `modifies` is the index (`i`) of that entity.

| Modifier | Attaches to | Signal examples |
| --- | --- | --- |
| `Negation` | a **Condition** | *no evidence*, *denies*, *without*, *ruled out* |
| `Laterality` | a **Locus** or **Intervention** | *right*, *left*, *bilateral* |
| `Sub_location` | a **Locus** | *extra*, *upper*, *lower*, *proximal* |

- Mark the **signal**, not the whole phrase: in *"no evidence of secondaries"*,
  the Negation span is *no evidence*; *secondaries* is the Condition it modifies.
- A single Laterality/Sub_location can sit before the Locus it modifies
  (*right* → *second toe*).

## 4. Span & boundary rules

- **Verbatim.** A span is an exact substring of the note — same words, same case,
  no paraphrase, no added/trimmed words. (Downstream, offsets are computed by
  *finding your span text in the frozen note*; a paraphrase can't be located and
  is lost.)
- **Maximal meaningful span.** Mark the largest clinically coherent unit:
  *fracture dislocation* as one Condition, not *fracture* + *dislocation*.
- **No overlaps between entity types.** One character belongs to at most one
  entity span. A modifier may sit *adjacent* to its entity but doesn't overlap it.
- **Measurements** attached to an Investigation are **Result** (*"12 x 5 cm"*).

## 5. Hard cases & conventions

These are the recurring judgment calls; resolve them the same way every time.

- **"myocardial infarction"** → a **single Condition**. Do *not* split into
  Condition + Locus. (CLEF flags this exact case; we always resolve to one span.)
- **"groin dissection"** → **two spans**: *groin* (Locus) + *dissection*
  (Intervention). A procedure named by its site is site-Locus + action-Entity,
  not one blob. Same for *"lymph node biopsy"* → *lymph node* (Locus) + *biopsy*
  (Investigation), and *"facial pain"* → *facial* (Locus) + *pain* (Condition).
- **Negation scope.** The Negation attaches to the Condition it denies, even when
  words intervene (*"no evidence of extra pelvic secondaries"* → Negation *no
  evidence* modifies Condition *secondaries*).
- **A test result that is a disease is a Condition, not a Result** (see §2 Result).
- **Coordinated lists** ("pain and swelling") → mark each conjunct as its own
  Condition span.
- **Don't annotate section headers or template scaffolding** (e.g. a bare
  "DIAGNOSIS:" label) — annotate the clinical content, not the form.

## 6. Fully worked example

The canonical CLEF passage (Roberts 2008, Tables 2–3), annotated. Relations are
shown *only for understanding* — they are **not** part of v1 output.

> This patient has had a **lymph node** *biopsy* which shows **melanoma** in his
> *right* **groin**. It is clearly **secondaries** from the **melanoma** on his
> *right* **second toe**. Although his **PET scan** is **normal** he does need a
> **groin** *dissection*. We agreed to treat with **DTIC**, and then consider
> **radiotherapy**. We will perform a **CT scan** to look at the *left* **pelvic
> side wall**. There was *no evidence* of *extra* **pelvic secondaries**. Her
> **facial** **pain** was initially relieved by **co-codamol**.

| Span (verbatim) | Label | modifies |
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

*(Implied relations, for context only, not annotated: biopsy `has_finding`
melanoma; melanoma `has_location` groin; PET scan `has_finding` normal;
dissection `has_target` groin; co-codamol `has_indication` pain.)*

## 7. Notes for LLM annotators

- **Copy span text verbatim** (§4). This is non-negotiable: offsets are recovered
  by string-matching your text against the frozen note.
- **Output JSON only**, no prose, no code fence — the exact shape in `SCHEMA.md`
  / the `annotate.py` prompt: `{"entities": [{"text","label","modifies?"}]}`, with
  `modifies` = the verbatim text of the modified entity.
- **Don't hallucinate spans**, and don't "normalize" text (no expanding
  abbreviations, no fixing typos) — mark what is written.
- **Determinism matters for evaluation.** Run at the temperature the pipeline
  will actually use; self-consistency across repeats is measured explicitly
  (`specs/compare.md`).

## 8. Where disagreement clusters — spend care accordingly

CLEF's inter-annotator agreement on narratives (strict IAA, Table 6) tells you
which labels are hard, so you know where to slow down:

- **Easy / high agreement:** Laterality (95%), Drug_or_device (84%), Condition
  (81%), Locus (78%). These rarely cause disputes.
- **Hard / low agreement — annotate deliberately:** Sub_location (63%),
  Intervention (64%), Negation (67%), Result (69%). Most disagreement here is the
  Investigation-vs-Intervention call (§2) and negation scope (§5).

## Source & versioning

CLEF scheme — Roberts et al. (2008), "Semantic Annotation of Clinical Text: The
CLEF Corpus", Tables 2–3 and §4.1. This guideline pairs with `SCHEMA.md` (labels)
and is distilled into `annotate.py`'s prompt (`PROMPT_VER`). Revise both together
after seeing real disagreements in the pilot.
