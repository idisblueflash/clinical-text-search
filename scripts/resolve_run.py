#!/usr/bin/env python3
"""Resolve offline annotations (from an agent or a human) into a run.

The OpenRouter path (annotate.py) and this path share the same offset logic:
an annotator emits VERBATIM entity substrings + labels (never character offsets),
and we locate each substring in the frozen doc to produce [start,end). This lets
a Claude Code agent, or a human, annotate without the API and still land a
run in the identical runs/<name>/ format that check_offsets.py and compare.py
consume.

Input:  <out>/raw/NNNN.json  — one per doc, {"entities":[{text,label,modifies?}]}
Output: <out>/predictions.jsonl + <out>/run.json

    uv run python scripts/resolve_run.py runs/opus-agent-r1 --model claude-opus-4-8 \
        --annotator "claude-code agent (Opus, not OpenRouter)" --run-tag r1 --role reference
"""
import sys, json, hashlib, argparse, pathlib
from datetime import datetime, timezone

from annotate import resolve, load_manifest, SCHEMA_VER   # reuse the offset resolver


def main():
    ap = argparse.ArgumentParser(description="Resolve offline (agent/human) annotations into a run.")
    ap.add_argument("out", help="run dir; expects <out>/raw/NNNN.json, writes predictions.jsonl + run.json")
    ap.add_argument("--dataset", default="datasets/mtsamples-ner-v1")
    ap.add_argument("--model", required=True, help="model/annotator id recorded in run.json, e.g. claude-opus-4-8")
    ap.add_argument("--annotator", help="human-readable annotator description")
    ap.add_argument("--run-tag", help="e.g. r1")
    ap.add_argument("--role", default="candidate", help="e.g. reference / candidate")
    ap.add_argument("--entities-only", action="store_true")
    args = ap.parse_args()

    out = pathlib.Path(args.out)
    raw = out / "raw"
    if not raw.is_dir():
        print(f"resolve_run: no raw/ dir at {raw}", file=sys.stderr); sys.exit(2)
    dataset = pathlib.Path(args.dataset)
    manifest = load_manifest(dataset)

    results, missing, malformed = [], [], []
    n_unlocated = 0
    for did in sorted(manifest):
        f = raw / f"{did}.json"
        if not f.exists():
            missing.append(did); continue
        try:
            obj = json.loads(f.read_text())
        except json.JSONDecodeError as e:
            malformed.append(f"{did}: {e}"); continue
        ents = obj.get("entities") if isinstance(obj, dict) else obj
        if not isinstance(ents, list):
            malformed.append(f"{did}: no entities list"); continue
        doc = (dataset / manifest[did]["text_file"]).read_text()
        if hashlib.sha256(doc.encode()).hexdigest() != manifest[did]["text_sha256"]:
            print(f"resolve_run: {did} sha != manifest — dataset not frozen, aborting.", file=sys.stderr)
            sys.exit(1)
        spans, n_unloc = resolve(ents, doc, entities_only=args.entities_only)
        n_unlocated += n_unloc
        results.append({"doc_id": did, "entities": spans})

    if not results:
        print("resolve_run: no annotations resolved — nothing to write.", file=sys.stderr); sys.exit(1)

    with open(out / "predictions.jsonl", "w") as fh:
        for r in results:
            fh.write(json.dumps(r) + "\n")
    run_meta = {
        "model": args.model,
        "annotator": args.annotator or args.model,
        "run_tag": args.run_tag,
        "role": args.role,
        "date": datetime.now(timezone.utc).isoformat(),
        "dataset": dataset.name,
        "schema_ver": SCHEMA_VER,
        "guideline": "guideline.md",
        "source": "offline annotations resolved via resolve_run.py",
        "entities_only": args.entities_only,
        "n_docs": len(results),
        "n_missing_docs": len(missing),
        "n_unlocated_spans": n_unlocated,
    }
    json.dump(run_meta, open(out / "run.json", "w"), indent=2)

    print(f"resolved {len(results)}/{len(manifest)} docs → {out}"
          f"  ({n_unlocated} unlocated spans)")
    if missing:
        print(f"  MISSING ({len(missing)}): {', '.join(missing[:20])}{' …' if len(missing) > 20 else ''}")
    if malformed:
        print(f"  MALFORMED ({len(malformed)}):")
        for m in malformed:
            print(f"    - {m}")
    if missing or malformed:
        sys.exit(1)


if __name__ == "__main__":
    main()
