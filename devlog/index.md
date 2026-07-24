---
reviewed: Yes
reviewed_by: Flash Hu
---

# devlog — clinical-annotation-tools

Engineering decision log. Newest entries on top. Each decision records the
*why*, not just the *what* (the code shows the what). "DEFERRED" marks things
knowingly left for later so nothing silently falls through.

Goal of the prototype: natural-language query → matching clinical narratives.
First build is the upstream piece — a clean, frozen NER dataset + a Claude
baseline — not the query/retrieval UI.

One file per dated entry under this folder. Newest first. Each records the
*why*, not just the *what*. See [backlog.md](backlog.md) for the running
deferred / not-done list.

## Entries (newest first)

- [2026-07-23 — gemma4 on the Mini via Ollama; FIRST self-consistency number](09-gemma4-ollama-self-consistency.md) — gemma4:e2b on the Mini via Ollama; FIRST self-consistency number (0.732) — its low silver score is systematic, not noise
- [2026-07-23 — Ollama client (local models on THIS Mac)](08-ollama-client.md) — stdlib Ollama client for local models on this Mac (num_predict + think gotchas)
- [2026-07-23 — LM Studio client (local models on the Mac Mini)](07-lmstudio-client.md) — stdlib LM Studio client for local models on the Mini (proxy + SSH-tunnel gotchas); first local candidate run
- [2026-07-23 — Sonnet via the AGENT path; the annotation PATH dominates the model](06-sonnet-agent-path-dominates.md) — Sonnet via the AGENT path; the annotation PATH matters more than the MODEL (0.736 vs 0.535)
- [2026-07-23 — full Sonnet run + compare.py built; first agreement vs silver](05-full-sonnet-run-compare-built.md) — built compare.py; first agreement vs the Opus silver (0.535 exact); dense notes need --max-tokens 12000
- [2026-07-23 — Opus silver-standard reference via PARALLEL agent batches](04-opus-silver-parallel-agents.md) — Opus silver reference via 8 parallel cold-start agent batches; guideline gaps surfaced
- [2026-07-23 — OpenRouter annotator + uv env + annotation guideline](03-openrouter-annotator-uv-guideline.md) — OpenRouter annotator + uv env + guideline.md; the verbatim-offset decision; the reasoning-model trap
- [2026-07-23 — self-consistency metric + compare.py spec  (spec only, not built)](02-self-consistency-metric-compare-spec.md) — why measure self-consistency first (reliability ceiling); compare.py spec (F1 not kappa; the temperature trap)
- [2026-07-23 — mtsamples-ner-v1 dataset + stratified sampler  (commit 41eb9b9)](01-mtsamples-ner-v1-dataset-sampler.md) — the frozen dataset: MTSamples cleaning, two-axis CLEF stratified sampler, schema, run format
