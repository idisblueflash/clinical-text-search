# Entity Schema — CLEF (Roberts et al. 2008)

The NER label set for `mtsamples-ner-v1`. Taken as-is from the CLEF corpus entity
scheme — Roberts et al. (2008), "Semantic Annotation of Clinical Text: The CLEF
Corpus", Table 2 (entities) and Figure 1 (modifiers). Source card:
`semantic-annotation-of-clinical-text/papers/roberts-2008-clef-corpus.md`.

Every model (Claude first; GPT / local later) uses **this exact set**, so runs are
comparable.

## Entity types (6) — span-level

| Label | Definition (CLEF Table 2) | Example span |
| --- | --- | --- |
| `Condition` | Symptom, diagnosis, complication, condition, problem, function/process, injury. | *melanoma*, *facial pain*, *fracture dislocation* |
| `Intervention` | Action performed by a clinician on a patient / Locus / Condition to change or treat a Condition. | *groin dissection*, *radiotherapy*, *ORIF* |
| `Investigation` | Interaction aimed at measuring or studying — **not** changing — a Condition. Has findings/interpretations. | *lymph node biopsy*, *PET scan*, *CT scan* |
| `Result` | The numeric or qualitative finding of an Investigation (excluding a Condition). | *normal*, *80mg*, *12 x 5.2 x 4.6 cm* |
| `Drug_or_device` | Usually a drug; occasionally a device (suture material, drains). | *co-codamol*, *Hemovac drain* |
| `Locus` | Anatomical structure/location, body substance, or physiologic function — typically the locus of a Condition. | *right groin*, *left pelvic side wall*, *C2* |

## Modifiers (3) — span-level, attached to an entity

CLEF marks these as separate spans (Figure 1 ovals) that modify an entity. For
this NER baseline we mark them as spans with a `modifies` pointer to the entity
they qualify (by that entity's span index).

| Label | Modifies | Definition | Example |
| --- | --- | --- | --- |
| `Negation` | Condition | Signals a Condition is negated or uncertain. | *no evidence* (of secondaries) |
| `Laterality` | Locus, Intervention | Sidedness: right / left / bilateral. | *right* (second toe) |
| `Sub_location` | Locus | Finer location: upper, lower, extra, etc. | *extra* (pelvic) |

## Out of scope for this NER baseline

CLEF **relations** (Table 3: `has_target`, `has_finding`, `has_indication`,
`has_location`, and the `Modifies` links as typed relations) are **relation
extraction** — a separate task that needs the entities above to be found first.
Not labeled in v1. Revisit as `mtsamples-re-v1` once the NER baseline is stable.

## Boundary rules (keep annotators and models consistent)

- Mark the **longest** clinically meaningful span (e.g. *fracture dislocation*,
  not *fracture* + *dislocation* apart) unless a modifier splits it.
- A word can carry a modifier **and** sit in an entity's context, but one
  character offset belongs to exactly one entity span (no overlap between two
  entity types). Modifiers may sit next to the entity they point at.
- "myocardial infarction" is a single `Condition` (CLEF flags this exact case as a
  judgment call; we make it one Condition, not Condition + Locus).
- Numeric measurements that belong to an Investigation are `Result`.

## Output format (per document, in a run's `predictions.jsonl`)

```json
{"doc_id": "0001",
 "entities": [
   {"i": 0, "start": 41, "end": 47, "text": "melanoma", "label": "Condition"},
   {"i": 1, "start": 55, "end": 60, "text": "right", "label": "Laterality", "modifies": 2},
   {"i": 2, "start": 61, "end": 66, "text": "groin", "label": "Locus"}
 ]}
```

`start`/`end` are character offsets into `docs/<doc_id>.txt` (half-open,
`[start, end)`). `i` is the span index within the doc; `modifies` (modifiers only)
points at the `i` of the entity it qualifies.
