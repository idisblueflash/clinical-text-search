---
reviewed: No
reviewed_by:
---

# 2026-07-23 — LM Studio client (local models on the Mac Mini)

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
