---
reviewed: No
reviewed_by:
---

# 2026-07-23 — OpenRouter annotator + uv env + annotation guideline

## Decision: annotate via OpenRouter (one API for all models)

- **scripts/annotate.py** runs the CLEF-schema NER prompt over the frozen dataset
  and writes runs/<model-slug>[-<tag>]/predictions.jsonl + run.json. Any model
  (Claude/GPT/local) goes through the SAME endpoint → directly serves both goals:
  self-consistency (repeat one model, --run-tag r1/r2/r3) and cross-model.
- **scripts/openrouter_client.py** is the reusable (model, text) -> (response,
  cost) primitive; annotate.py is built on it, and it runs standalone as a CLI.
- **Library = `openrouter` PyPI SDK** (client.chat.send), per user direction. It
  is a Speakeasy-generated SDK; cost comes back on res.usage.cost. Introspected
  the installed package to code against the real API (send kwargs, ChatResult).

## THE offset decision (correctness-critical)

- LLMs cannot reliably emit character offsets. So the model returns VERBATIM
  entity substrings + labels, and annotate.py locates each in the frozen doc to
  produce [start,end). Unlocatable spans kept with start/end=null + located:false
  and counted (n_unlocated_spans) — surfaced, never silently dropped. Verified
  the resolver on doc 0001: real spans byte-match, fake span flagged, modifier
  `modifies` maps to the target entity's index. Entities resolved before
  modifiers so modifier pointers can resolve.
- Consequence for the prompt: "copy text verbatim" is load-bearing, not style.

## Env: uv

- Adopted `uv` (uv.lock committed). Requires-python >=3.11. ONE runtime dep,
  `openrouter`; the data pipeline (build_dataset.py) stays stdlib-only — the
  stdlib-only rule now scopes to the pipeline, not the whole repo. CLAUDE.md and
  pyproject comment updated to match (they previously said "stdlib only" repo-wide).

## Guideline: guideline.md (humans + LLMs)

- Wrote guideline.md from the CLEF paper (Roberts 2008, Tables 2-3 + §4.1): the
  annotation *process* — a recipe (ordered passes to avoid omission), decision
  cues (esp. Investigation-vs-Intervention), modifier attachment, boundary rules,
  hard-case conventions (myocardial infarction = 1 Condition; groin dissection =
  Locus+Intervention), a fully worked example, and where IAA says disagreement
  clusters. It pairs with SCHEMA.md (labels) and is DISTILLED into annotate.py's
  SYSTEM_PROMPT — change guideline => bump PROMPT_VER (comparability key).

## First live run (Sonnet 5, 3 docs) + the reasoning-model trap

- Ran anthropic/claude-sonnet-5 over 3 docs. FIRST ATTEMPT: all 3 failed to parse
  ("no JSON object" / truncated JSON) yet still cost $0.13. Root cause: **Sonnet 5
  defaults to extended thinking** — completion_tokens hit the 4000 cap entirely as
  reasoning (reasoning_details full, content=None, finish_reason=length). Not a
  prompt bug; the model never emitted an answer.
- FIX: added `reasoning_effort` passthrough (openrouter_client.chat + annotate.py
  `--reasoning`, DEFAULT 'none'). Re-ran: 3/3 parsed, 233 spans, $0.071, offsets
  verify against docs, labels sensible (Condition/Result/Intervention/Locus/
  Negation). 1/233 unlocated = a duplicate emission of "excision margin" (occurs
  once in text; surplus mention gets no distinct offset) — correct conservative
  behavior, not a bug. run.json now records reasoning_effort.
- LESSON: any thinking model needs reasoning off (or a much larger token budget)
  for extraction, or it returns empty content. Documented in manual/annotate.md.
- Output dir: runs/anthropic-claude-sonnet-5/ (committed? — it's a real run, keep).

DEFERRED (this entry): only 3 docs run (pilot); scale to 80 after eyeballing span
quality. compare.py still unbuilt (specced).
