---
reviewed: No
reviewed_by:
---

# `lmstudio_client.py` — list & prompt local LM Studio models

`scripts/lmstudio_client.py` talks to a **local** [LM Studio](https://lmstudio.ai)
server — list the models it has, or send one a prompt. It is the same small
`(model, text) → reply` helper as [`openrouter_client.md`](openrouter_client.md),
but the model runs on your own machine (here, the **Mac Mini**), so there is **no
API key and no dollar cost**. Good for cheap local candidate runs (e.g.
`qwen3-0.6b-mlx`) to compare against the silver standard.

Stdlib only — no extra dependency. LM Studio speaks the OpenAI-compatible REST
API, which is plain JSON over HTTP.

## What it does

- `--list` — print the model ids LM Studio currently has available.
- `--model X --text "..."` — send a prompt to model `X`, print the reply.

## First: reach the Mac Mini (SSH tunnel)

LM Studio binds to **its own machine's localhost** by default, so the Mini's
server is not on the network. Open an SSH tunnel so `localhost:1234` here forwards
to the Mini, then leave it running:

```
ssh -f -N -L 1234:localhost:1234 macmini     # -f backgrounds it; kill it when done
```

Check it is up (this bypasses any local proxy, see Gotchas):

```
curl -s http://localhost:1234/v1/models | head
```

To stop the tunnel later: `pkill -f 'ssh.*-L 1234:localhost:1234 macmini'`.

(Alternative: set LM Studio to *Serve on Local Network* and point `--base-url` /
`LMSTUDIO_BASE_URL` at the Mini's IP, e.g. `http://10.62.1.190:1234/v1`. The
tunnel is preferred — it needs no LM Studio change and is not exposed on the LAN.)

## Usage

```
uv run python scripts/lmstudio_client.py --list
uv run python scripts/lmstudio_client.py --model <id> (--text "..." | --text-file f | < stdin)
```

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `--list` | — | List available models and exit. |
| `--model ID` | — | Model id (from `--list`), e.g. `qwen3-0.6b-mlx`. Required unless `--list`. |
| `--text STR` | — | Prompt text. |
| `--text-file F` | — | Read the prompt from a file. (Or pipe text on stdin.) |
| `--system STR` / `--system-file F` | — | System prompt. |
| `--temperature F` | `0.0` | Sampling temperature. |
| `--max-tokens N` | model default | Cap the reply length. |
| `--base-url URL` | `http://localhost:1234/v1` | LM Studio server. Or set `LMSTUDIO_BASE_URL`. |
| `--timeout SEC` | `120` | Request timeout. |

## Examples (real output)

### List what the Mini has loaded

```
$ uv run python scripts/lmstudio_client.py --list
# 8 model(s) at http://localhost:1234/v1
qwen/qwen3-1.7b
deepseek-ocr-2
whisper-large-v3-turbo
qwen/qwen3-vl-4b
text-embedding-nomic-embed-text-v1.5
text-embedding-qwen3-embedding-0.6b
qwen3-embedding-0.6b-dwq
qwen3-0.6b-mlx
```

### Prompt a model

```
$ uv run python scripts/lmstudio_client.py --model qwen3-0.6b-mlx \
    --text 'Name three vital signs. /no_think' --max-tokens 200
Three vital signs are:

1. **Heart Rate (HR)** – Measures how fast the heartbeats.
2. **Respiratory Rate (RR)** – Measures how many times you breathe in.
3. **Systolic Blood Pressure** – The highest blood pressure during a heartbeat.
```

### As a library

```python
from lmstudio_client import chat, list_models
list_models()                                  # ['qwen3-0.6b-mlx', ...]
chat("qwen3-0.6b-mlx", "Summarize: ...", system="You are terse.")
```

## Gotchas

- **A local proxy will break it — the client already handles this.** This Mac has
  an HTTP proxy (`HTTP_PROXY=http://127.0.0.1:7897`). Python's `urllib` would send
  even `localhost` through it and get **`502 Bad Gateway`**. The client builds its
  own opener with proxies disabled, so it always connects directly. If you hit a
  502 from other tools, that proxy is why — `curl` bypasses it for local hosts.
- **502 right after opening the tunnel** = the tunnel is not ready yet. Wait a
  second (or poll `curl .../v1/models`) before the first call.
- **Model not in `--list`** (e.g. `google/gemma-3-1b`) = it is not downloaded on
  the Mini. Load it in the LM Studio app first, then it shows in `--list`.
- **Qwen3 is a reasoning model.** It emits a hidden `<think>` block by default,
  which eats the token budget. Append **`/no_think`** to the prompt to skip it (as
  above), or raise `--max-tokens`. If `content` comes back empty because the model
  only produced reasoning, the client falls back to `reasoning_content` so you
  still get output.
- **Small models are weak.** `qwen3-0.6b` / `1.7b` are tiny — fine for wiring and
  smoke tests, but expect low NER quality vs the Opus/Sonnet runs.
```
