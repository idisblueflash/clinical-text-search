---
reviewed: No
reviewed_by:
---

# devlog — clinical-annotation-tools

Engineering decision log. Newest entries on top. Each decision records the
*why*, not just the *what* (the code shows the what). "DEFERRED" marks things
knowingly left for later so nothing silently falls through.

Goal of the prototype: natural-language query → matching clinical narratives.
First build is the upstream piece — a clean, frozen NER dataset + a Claude
baseline — not the query/retrieval UI.

================================================================================
2026-07-23 — gemma4 on the Mini via Ollama; FIRST self-consistency number
================================================================================

## Decision: put gemma4:e2b on the Mini via Ollama (not LM Studio)

- gemma4:e2b is an OLLAMA-NATIVE model (arch "gemma4", multimodal vision+audio+
  thinking, 5.1B / E2B effective, needs Ollama 0.20+). LM Studio (llama.cpp/MLX)
  can't load Ollama's blob, so "same model in LM Studio" isn't a copy — chose to
  run Ollama on the Mini instead (exact same weights; plugs into --provider ollama).
- Wired --provider ollama into annotate.py (3rd backend: openrouter/lmstudio/ollama),
  same SYSTEM_PROMPT + offset resolver. num_predict <- max_tokens; --no-think sends
  Ollama's think:false. run.json records provider+base_url.

## Getting the model onto the Mini — internet pull FAILED, LAN rsync WON

- Mini had no Homebrew/Ollama. Installed headless: curl the macOS app zip (176MB),
  unzip, run the bundled CLI at Ollama.app/Contents/Resources/ollama (xattr -dr
  com.apple.quarantine first so Gatekeeper doesn't block it). `ollama serve` detached.
- `ollama pull gemma4:e2b` (7.2GB) DIED at 8%: ~2 MB/s then a DNS failure on Ollama's
  Cloudflare R2 CDN ("no such host") — same flaky-Mini-internet as the earlier HF/LM
  Studio downloads. Retrying would likely fail again.
- FIX: skip the internet. This Mac already had gemma4:e2b, so rsync ~/.ollama/models/
  Mac -> Mini over the LAN (fast, no CDN/DNS). Gotcha: macOS ships openrsync/old rsync
  — `--info=progress2` is unsupported and printed usage instead of running; plain
  `rsync -a` worked. gemma4:e2b now native on the Mini. Reached via SSH tunnel on LOCAL
  port 11435 (11434 is THIS Mac's own Ollama) -> --base-url http://localhost:11435.

## RESULT: first self-consistency number (gemma4 x3 @ temp 0.7)

- Ran gemma4 THREE times, --run-tag r1/r2/r3, at temp 0.7 (NOT 0 — specs/compare.md:
  temp 0 => self-F1 ~ 1.0, measures nothing; 0.7 shows real sampling noise). ~13
  min/run on the Mini (E2B is fast, unlike the 7B). Offsets OK all three.
- SELF-CONSISTENCY = 0.732 mean pairwise micro-F1 [min 0.710, max 0.755, sd 0.023].
  So gemma4 agrees with ITSELF only ~0.73 across repeats — ~27% of its output is
  random run-to-run noise at 0.7. (Failed-doc counts also varied: 11/16/7 — same
  instability. compare.py scored the shared non-failed docs, gaps reported.)
- gemma4-r1 vs Opus silver = 0.163 exact (prec 0.094 / rec 0.583). gemma4 total spans
  = 764 (vs Opus ~5562) — heavy UNDER-annotation.
- THE POINT of measuring self-consistency FIRST: it's the reliability ceiling. gemma4's
  silver score 0.163 << its own ceiling 0.732, so its poor result is SYSTEMATIC (it's
  consistently different from Opus: under-annotates, different boundaries), NOT just
  noise. Without the ceiling you couldn't split "bad-because-unstable" from
  "bad-because-consistently-different"; it's the latter. Modifier by-type here is
  low-count/unreliable (Negation/Sub_location show 1.0 = "both emit none" agreeing).

## Local-candidate landscape vs the Opus silver (all via the annotate.py path)

- qwen2.5-7b (Mini/LM Studio, temp 0): 0.190 exact. But 14/80 docs FAILED (dense-note
  timeouts even at 300s on the 16GB M4) and 269 unlocated (heavy rewording); 99 min.
- gemma4:e2b (Mini/Ollama): 0.163, self-consistency 0.732, fast, no timeouts.
- qwen3-1.7b: 0.075. gemma-3-1b / qwen3-0.6b: unusable (0 valid spans — echo the
  prompt's placeholders, runaway JSON).
- TAKEAWAY: 5-7B local models cluster at 0.16-0.19 vs silver — far below frontier
  (agent-Sonnet 0.736). A capable local candidate needs a bigger model than the 16GB
  Mini comfortably runs. gemma4 (E2B) is the best speed/quality/stability tradeoff of
  the local set and runs fine on the Mini.

DEFERRED: (a) self-consistency for the FRONTIER models (Opus/Sonnet x3) to get their
ceilings too — needed to read the silver F1s as "how close" vs "how noisy"; (b) a
mid/large local model if a real local candidate is wanted; (c) qwen2.5-7b timeouts —
raise --timeout or accept dense-note gaps.

================================================================================
2026-07-23 — Ollama client (local models on THIS Mac)
================================================================================

- scripts/ollama_client.py: same small (model,text)->reply helper as
  lmstudio_client.py, but for a local Ollama server (on this Mac, port 11434 — no
  tunnel, unlike LM Studio on the Mini). STDLIB ONLY (urllib) over Ollama's native
  REST (/api/tags, /api/chat) — the same API the `ollama` python pkg wraps; chose
  plain HTTP to add no dep and keep the proxy-bypass in our own hands (the Clash
  proxy at 127.0.0.1:7897 would hijack localhost — same trap as LM Studio).
- Two Ollama specifics: (1) num_predict defaults to just 128 tokens -> truncates a
  long NER reply; the CLI exposes --num-predict (use -1 for no cap). (2) think: a
  thinking model (gemma4:e2b is one) burns budget reasoning; --no-think sends
  think:false (only sent when asked, so non-thinking models don't error).
- Available locally: gemma4:e2b (5.1B, Q4_K_M, thinking) and qwen3.5:0.8b. Verified
  --list + a gemma prompt return sensibly. "gemma" per the user = gemma4:e2b.
- DEFERRED: wire ollama into annotate.py as a 3rd --provider (like lmstudio) for a
  gemma4:e2b candidate run -> compare vs silver. gemma4 is 5B, so a plausible
  candidate (unlike the 1B floor models); worth a run if wanted.

================================================================================
2026-07-23 — LM Studio client (local models on the Mac Mini)
================================================================================

## Decision: a stdlib client for LOCAL models via LM Studio (no API cost)

- Driver: run tiny/local models (qwen3-0.6b-mlx, qwen/qwen3-1.7b, …) hosted in
  LM Studio on the Mac Mini as cheap candidates — the "local model" path the
  dataset was always meant to accept. LM Studio speaks the OpenAI-compatible REST
  API, so scripts/lmstudio_client.py is the same small (model,text)->reply helper
  as openrouter_client.py but points at a local server.
- STDLIB ONLY (urllib) — no new dep. LM Studio's endpoints are plain JSON over
  HTTP (GET /v1/models, POST /v1/chat/completions). Keeps the stdlib-only spirit;
  the annotation dep stays just `openrouter`. CLI: --list, or --model + prompt.

## Two gotchas that cost debugging time (documented in the manual)

1. **A local HTTP proxy 502s localhost.** This Mac has HTTP_PROXY=127.0.0.1:7897
   (Clash-style). Python urllib routes EVEN localhost through it -> 502 Bad Gateway,
   while curl bypasses it for local hosts (so curl worked but the client didn't).
   FIX: the client builds its own opener with an empty ProxyHandler, so it always
   connects directly. This is the correct behavior for a local endpoint.
2. **LM Studio binds to the Mini's localhost, not the LAN.** Reach it with an SSH
   tunnel: `ssh -f -N -L 1234:localhost:1234 macmini` (Mini IP is 10.62.1.190 if
   ever set to serve on-network, but tunnel is preferred — no LM Studio change, not
   LAN-exposed). A 502 right after opening the tunnel = not ready yet; wait/poll.

## Notes

- qwen3 is a REASONING model: emits a hidden <think> block that eats max_tokens.
  Append `/no_think` to the prompt (Qwen convention) or raise --max-tokens. Client
  falls back to reasoning_content if content is empty (same trap as the OpenRouter
  Sonnet path). Verified: --list (8 models) + prompts to 0.6b/1.7b return sensibly.
- google/gemma-3-1b (user's other example) is NOT downloaded on the Mini yet — only
  the Qwen models are loaded; load it in the LM Studio app to make it appear.

## DONE: wired lmstudio into annotate.py (--provider) + ran a local NER candidate

- annotate.py gained `--provider {openrouter,lmstudio}` + `--base-url` + `--no-think`.
  Both providers share the SAME SYSTEM_PROMPT and verbatim-offset resolver, so a
  local run lands in the identical runs/<model>/ format. run.json records provider +
  base_url. No fork; one command, two backends.
- qwen3-0.6b-mlx is UNUSABLE for this task: with the standard prompt it returned the
  literal word "ENTITIES" as every label (0 valid spans after schema filter) and broke
  JSON on long docs. Did NOT run it on all 80 — pilot (3 docs) was conclusive; would
  have been an empty run. (User chose to switch to 1.7b instead.)
- qwen/qwen3-1.7b RAN on all 80 (no_think, max_tokens 8000): $0.00, 12 min, 3 parse
  failures (0009/0027/0028, the densest), 606 spans / 511 located / 95 UNLOCATED.
  Offsets check OK. vs Opus silver: 0.075 exact / 0.131 relaxed F1. vs API-Sonnet
  (SAME path): 0.084 exact — so it's model weakness, not a path artifact.
- WHY so low: qwen UNDER-annotates massively — 606 spans vs Opus ~5562 / Sonnet ~6500
  (finds ~4% of what they find), and rewords instead of copying verbatim (95/606
  unlocated). Relaxed recall on qwen's own spans is 0.75 (when it fires, the span is in
  a sensible place), but it fires rarely. A 1.7B local model is far below frontier for
  clinical NER — a rough FLOOR. The harness itself worked end-to-end on a free, local
  model, which was the point.

DEFERRED: (a) a mid-size local model (7-8B) would be the real cheap-candidate test —
1.7B is too small; (b) load gemma-3-1b if a same-size cross-arch point is wanted (also
expected weak); (c) tiny models might do better with a simplified, one-shot prompt, but
that = a new PROMPT_VER (breaks comparability with the frontier runs) — only if the goal
is "best local extraction", not "compare on the shared prompt".

================================================================================
2026-07-23 — Sonnet via the AGENT path; the annotation PATH dominates the model
================================================================================

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

================================================================================
2026-07-23 — full Sonnet run + compare.py built; first agreement vs silver
================================================================================

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

================================================================================
2026-07-23 — Opus silver-standard reference via PARALLEL agent batches
================================================================================

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

================================================================================
2026-07-23 — OpenRouter annotator + uv env + annotation guideline
================================================================================

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

================================================================================
2026-07-23 — self-consistency metric + compare.py spec  (spec only, not built)
================================================================================

## Decision: measure model self-consistency first, via compare.py

Before trusting any accuracy number, measure whether a model is *stable* across
repeated runs on the identical frozen bytes. Full design: `specs/compare.md`.

- **It's self-consistency (test-retest), NOT IAA.** IAA is between *different*
  annotators; same-model-repeated is intra-annotator / test-retest reliability.
  Three distinct metrics, one tool:
    * self-consistency   — model vs itself (r1/r2/r3) — *is it stable?*  ← now
    * cross-model agree   — Claude vs GPT vs local     — *do they converge?*
    * accuracy vs gold    — model vs human gold         — *is it right?*
  All three are the same operation: span-level F1 between two predictions files.
- **WHY first:** self-consistency is the RELIABILITY CEILING — a model can't
  agree with gold (or another model) more than it agrees with itself. Without it,
  a 0.75-vs-gold could be pure noise. It also splits error into random (unstable)
  vs systematic (wrong the same way every time). Driver: some local models are
  suspected inconsistent; this quantifies it instead of eyeballing.
- **Metric = pairwise span-level F1, NOT kappa.** Span extraction has no fixed
  item set and no countable negative class, so chance-corrected kappa is
  ill-defined. F1 is symmetric for matched-span counting, so it IS the agreement
  measure. K=3 runs → mean ± spread over the 3 pairs; per-entity-type breakdown
  (Locus/Negation less stable than Drug_or_device); exact + relaxed match to
  separate boundary disagreement from label flips. Modifiers scored in a separate
  pass (their `modifies` index is run-local).
- **THE TRAP (temperature).** The estimate is only meaningful if runs are
  identical except sampling noise. Fix + record temperature/top_p/seed in every
  run.json. At temp=0 most models are near-deterministic → self-F1 ≈ 1.0 measures
  nothing; run at PRODUCTION temperature so measured noise = pipeline's real
  noise. compare.py warns if these differ across runs.
- **Near-free given existing design.** runs/<model>/ already supports multiple
  runs (r1/r2/r3); compare.py is the deferred eval harness, now specced. N=80
  docs = hundreds of spans, ample for a stability estimate.

DEFERRED (unchanged): compare.py itself not yet built; Krippendorff α over BIO
and accuracy-vs-gold both out of scope until there's a reason / a gold set.

================================================================================
2026-07-23 — mtsamples-ner-v1 dataset + stratified sampler  (commit 41eb9b9)
================================================================================

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

--------------------------------------------------------------------------------
DEFERRED / NOT DONE / PASSED TO LATER
--------------------------------------------------------------------------------

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
