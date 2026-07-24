#!/usr/bin/env python3
"""Minimal LM Studio client — list local models, or give one a prompt.

LM Studio (https://lmstudio.ai) serves an OpenAI-compatible REST API, so this is
the same small (model, text) -> reply primitive as openrouter_client.py, but it
talks to a LOCAL server instead of a paid API. No API key, no dollar cost — the
model runs on your own machine (here, the Mac Mini). Good for cheap/local
candidate runs (e.g. qwen3-0.6b-mlx) to compare against the silver standard.

Stdlib only (urllib) — LM Studio's endpoints are plain JSON over HTTP, so this
adds no dependency.

Where the server is (LMSTUDIO_BASE_URL, default http://localhost:1234/v1):
LM Studio binds to its own machine's localhost by default. To reach one on the
Mac Mini from here, open an SSH tunnel first (localhost:1234 -> the Mini):

    ssh -N -L 1234:localhost:1234 macmini &      # leave running; Ctrl-C / kill to stop

Then the default base URL just works. Or point at any host with --base-url /
LMSTUDIO_BASE_URL (e.g. if LM Studio is set to serve on the network).

Use as a library:
    from lmstudio_client import chat, list_models
    reply = chat("qwen3-0.6b-mlx", "Summarize: ...", system="You are terse.")

or standalone from the shell:
    uv run python scripts/lmstudio_client.py --list
    uv run python scripts/lmstudio_client.py --model qwen3-0.6b-mlx --text "Hello"
    uv run python scripts/lmstudio_client.py --model qwen/qwen3-1.7b --text-file note.txt
"""
import os, sys, json, argparse, urllib.request, urllib.error

DEFAULT_BASE_URL = "http://localhost:1234/v1"

# LM Studio is a LOCAL server (often reached over an SSH tunnel to localhost). Any
# ambient HTTP proxy (e.g. a Clash proxy at 127.0.0.1:7897, or a corporate one) must
# NOT be used for it — routing localhost through a proxy returns 502. This opener
# has an empty ProxyHandler, so it always connects directly.
_OPENER = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def base_url(explicit=None):
    return (explicit or os.environ.get("LMSTUDIO_BASE_URL") or DEFAULT_BASE_URL).rstrip("/")


def _post(url, payload, timeout):
    req = urllib.request.Request(
        url, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"}, method="POST")
    with _OPENER.open(req, timeout=timeout) as r:
        return json.load(r)


def _get(url, timeout):
    with _OPENER.open(url, timeout=timeout) as r:
        return json.load(r)


def _unreachable(base, err):
    return RuntimeError(
        f"cannot reach LM Studio at {base} ({err}). Is the server running, and — "
        f"for a Mini — is the SSH tunnel open? (ssh -N -L 1234:localhost:1234 macmini)")


def list_models(*, base=None, timeout=30):
    """Return the ids of the models LM Studio currently has available."""
    b = base_url(base)
    try:
        data = _get(f"{b}/models", timeout)
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        raise _unreachable(b, e)
    return [m["id"] for m in data.get("data", [])]


def chat(model, text, *, system=None, temperature=0.0, max_tokens=None,
         base=None, timeout=120):
    """Send one (model, text) turn to a local LM Studio model. Return the reply.

    `system` is an optional system prompt. LM Studio auto-loads the model on first
    request if it is downloaded (JIT); an id it does not have raises an error.
    For a reasoning model (e.g. qwen3) the visible answer is in `content`; if the
    model spent the whole turn thinking and left `content` empty, we fall back to
    the `reasoning_content` LM Studio returns, so the caller never gets ''."""
    b = base_url(base)
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": text})
    payload = {"model": model, "messages": messages,
               "temperature": temperature, "stream": False}
    if max_tokens is not None:
        payload["max_tokens"] = max_tokens
    try:
        res = _post(f"{b}/chat/completions", payload, timeout)
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"LM Studio {e.code} for model {model!r}: {detail}")
    except (urllib.error.URLError, ConnectionError, OSError) as e:
        raise _unreachable(b, e)
    choices = res.get("choices") or []
    if not choices:
        return ""
    msg = choices[0].get("message", {})
    return (msg.get("content") or msg.get("reasoning_content") or "").strip()


def main():
    ap = argparse.ArgumentParser(description="List local LM Studio models, or prompt one.")
    ap.add_argument("--list", action="store_true", help="list available models and exit")
    ap.add_argument("--model", help="model id (see --list), e.g. qwen3-0.6b-mlx")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--text", help="prompt text")
    g.add_argument("--text-file", help="read prompt text from a file")
    ap.add_argument("--system", help="system prompt text")
    ap.add_argument("--system-file", help="read system prompt from a file")
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--max-tokens", type=int)
    ap.add_argument("--base-url", help=f"LM Studio base URL (default {DEFAULT_BASE_URL}; "
                                       f"or set LMSTUDIO_BASE_URL)")
    ap.add_argument("--timeout", type=int, default=120, help="seconds (default 120)")
    args = ap.parse_args()

    try:
        if args.list:
            models = list_models(base=args.base_url, timeout=args.timeout)
            print(f"# {len(models)} model(s) at {base_url(args.base_url)}")
            for m in models:
                print(m)
            return

        if not args.model:
            ap.error("--model is required (unless --list)")
        if args.text is None and args.text_file is None and sys.stdin.isatty():
            ap.error("give a prompt via --text, --text-file, or stdin")
        if args.text is not None:
            text = args.text
        elif args.text_file is not None:
            text = open(args.text_file).read()
        else:
            text = sys.stdin.read()
        system = open(args.system_file).read() if args.system_file else args.system

        reply = chat(args.model, text, system=system, temperature=args.temperature,
                     max_tokens=args.max_tokens, base=args.base_url, timeout=args.timeout)
    except Exception as e:
        print(f"lmstudio_client: {e}", file=sys.stderr)
        sys.exit(1)
    print(reply)


if __name__ == "__main__":
    main()
