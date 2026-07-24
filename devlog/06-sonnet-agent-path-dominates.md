---
reviewed: No
reviewed_by:
---

# 2026-07-23 — Sonnet via the AGENT path; the annotation PATH dominates the model

## Decision: run Sonnet as agents, not the OpenRouter API (cost + fairness)

- Driver: the OpenRouter Sonnet run costs real $ (~$2/run). The agent path (harness
  model, no API charge) is free and was already built for the Opus reference. Ran
  Sonnet the SAME way: 8 parallel cold-start agents (model: sonnet), ~10 docs each,
  verbatim text+label to runs/sonnet-agent-r1/raw/, then resolve_run.py + check_offsets.
- Result: 80/80 resolved, 7421/7490 spans verified, 69 unlocated (dup mentions), 0
  problems. role=candidate. Denser than both the API-Sonnet run (6953 spans) and Opus
  (6216) — agents read the FULL guideline and tag more exhaustively.

## FINDING: the annotation PATH matters more than the MODEL

Three comparisons, exact-match entity F1:
  - API-Sonnet     vs Opus-agent  (diff model, diff path) = 0.535  (0.735 relaxed)
  - AGENT-Sonnet   vs Opus-agent  (diff model, SAME path) = 0.736  (0.811 relaxed)
  - AGENT-Sonnet   vs API-Sonnet  (SAME model, diff path) = 0.502

- Two *Sonnets* through different paths agree only 0.502 — LESS than Sonnet-agent
  agrees with Opus-agent (0.736). So the PATH (full guideline.md+SCHEMA.md read by an
  agent vs annotate.py's DISTILLED SYSTEM_PROMPT over the API) moves the annotations
  more than the model choice does.
- Consequence: the earlier 0.535 "Sonnet vs Opus" (prev entry) was CONFOUNDED — it
  measured API-prompt-vs-full-guideline as much as Sonnet-vs-Opus. The clean, same-path
  number is 0.736: Sonnet-via-agent is much closer to the Opus reference than the API
  run implied. Modifiers especially: 0.165 -> 0.510 exact (the full guideline explains
  modifier attachment; the distilled prompt loses it).
- METHOD RULE going forward: compare runs made the SAME way. For candidate-vs-reference,
  prefer the agent path for both so the score reflects the model, not the prompt. The
  API path (annotate.py) stays for models with no agent (GPT/local) and for
  self-consistency ×N — but note the path when comparing across it.
- CAVEAT unchanged: still silver, and Sonnet is Opus's family (correlated bias reads
  high). 0.736 is agreement, not accuracy. The by-type weak spots persist across paths:
  Result (0.55) and Intervention (0.57) exact — real boundary/label ambiguity, not path.

DEFERRED: (a) the guideline gaps the agents re-flagged (vitals/device/dose scope,
Laterality-on-Condition) drive the remaining disagreement — harden guideline v2;
(b) cross-family candidate (GPT via API) still needed to cut same-family bias — accept
it runs through the API path, or build an agent path for it; (c) human-anchor subset.
