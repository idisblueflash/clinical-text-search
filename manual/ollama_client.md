---
reviewed: No
reviewed_by:
---

# `ollama_client.py` — list & prompt local Ollama models

`scripts/ollama_client.py` talks to a **local** [Ollama](https://docs.ollama.com)
server — list the models it has, or send one a prompt. Same small
`(model, text) → reply` helper as [`openrouter_client.md`](openrouter_client.md)
and [`lmstudio_client.md`](lmstudio_client.md), but the model runs on your own
machine, so there is **no API key and no dollar cost**.

Stdlib only — no extra dependency. It speaks Ollama's native REST API
(`GET /api/tags`, `POST /api/chat`), which is the same API the `ollama` Python
package wraps.

## What it does

- `--list` — print the model names Ollama has locally (like `ollama list`).
- `--model X --text "..."` — send a prompt to model `X`, print the reply.

## Where the server is

Ollama listens on `http://localhost:11434` by default — on **this Mac**, no tunnel
needed (unlike LM Studio on the Mini). Point elsewhere with `--base-url` or
Ollama's own `OLLAMA_HOST` env var (a bare `host:port` is fine — the scheme is
added). Start the server with `ollama serve` if it is not running.

## Usage

```
uv run python scripts/ollama_client.py --list
uv run python scripts/ollama_client.py --model <name> (--text "..." | --text-file f | < stdin)
```

## Options

| Option | Default | What it does |
| --- | --- | --- |
| `--list` | — | List local models and exit. |
| `--model NAME` | — | Model name (from `--list`), e.g. `gemma4:e2b`. Required unless `--list`. |
| `--text STR` | — | Prompt text. |
| `--text-file F` | — | Read the prompt from a file. (Or pipe text on stdin.) |
| `--system STR` / `--system-file F` | — | System prompt. |
| `--temperature F` | `0.0` | Sampling temperature. |
| `--num-predict N` | Ollama default (**128**) | Max output tokens. **Raise it** — 128 truncates a long reply; `-1` = no cap. |
| `--no-think` | off | Disable the reasoning pass on a thinking model (e.g. `gemma4`). |
| `--base-url URL` | `http://localhost:11434` | Ollama server (or `OLLAMA_HOST`). |
| `--timeout SEC` | `120` | Request timeout. |

## Examples (real output)

### List local models

```
$ uv run python scripts/ollama_client.py --list
# 2 model(s) at http://localhost:11434
gemma4:e2b
qwen3.5:0.8b
```

### Prompt gemma

```
$ uv run python scripts/ollama_client.py --model gemma4:e2b --no-think --num-predict 300 \
    --system "You are terse. Answer in one sentence." \
    --text "What is clinical named-entity recognition?"
Clinical named-entity recognition is the process of identifying and extracting specific medical terms and concepts from clinical text.
```

### As a library

```python
from ollama_client import chat, list_models
list_models()                                       # ['gemma4:e2b', 'qwen3.5:0.8b']
chat("gemma4:e2b", "Summarize: ...", system="You are terse.", think=False)
```

## Gotchas

- **Raise `--num-predict`.** Ollama caps output at **128 tokens** by default, which
  silently truncates a long NER reply into broken JSON. Set a large value (or `-1`).
- **A local proxy would break it — the client already handles this.** This Mac has
  an HTTP proxy (`HTTP_PROXY=http://127.0.0.1:7897`); Python's `urllib` would route
  even `localhost` through it and fail. The client disables proxies for the
  connection, so it always connects directly.
- **Thinking models: use `--no-think`.** `gemma4:e2b` can spend its budget on a
  hidden reasoning pass; `--no-think` turns it off (the equivalent of
  `--reasoning none` / LM Studio's `/no_think`). If a model has no thinking mode,
  the flag is simply ignored on our side (we only send `think` when you ask).
- **Small models are weak at NER.** `gemma4:e2b` (5B) / `qwen3.5:0.8b` are fine for
  wiring and smoke tests, but expect low quality vs the Opus/Sonnet runs — the
  local floor (see `devlog.md`).
```
