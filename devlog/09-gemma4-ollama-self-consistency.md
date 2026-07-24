---
reviewed: No
reviewed_by:
---

# 2026-07-23 — gemma4 on the Mini via Ollama; FIRST self-consistency number

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
