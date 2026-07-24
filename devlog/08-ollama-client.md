---
reviewed: No
reviewed_by:
---

# 2026-07-23 — Ollama client (local models on THIS Mac)

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
