#!/usr/bin/env python3
"""Compare two (or more) runs span-by-span over the same frozen dataset.

One tool, three uses (all the same operation — span-level F1 between two
predictions.jsonl files, see specs/compare.md):
  * self-consistency  — the same model repeated (r1 vs r2 vs r3): is it steady?
  * run-vs-run agree  — different models (Sonnet vs the Opus reference): do they agree?
  * accuracy vs gold  — a run vs a human gold set, once one exists (same code).

Why F1, not kappa: span extraction has no fixed item list and no countable
negative class, so chance-corrected kappa is ill-defined. Span-level F1 counts
matched spans and is symmetric, so it IS the agreement measure.

Matching:
  * exact    — same [start,end) AND same label.
  * relaxed  — spans overlap AND same label (isolates boundary vs label disagreement).
Modifiers (Negation/Laterality/Sub_location) are scored in a SEPARATE pass: a
modifier match counts only once its target entity also matches across the runs
(its `modifies` pointer is an index into that run's own entity list).

Checks fail loudly BEFORE scoring — never score bad data (see specs/compare.md):
same frozen bytes (sha256), offset sanity (doc[start:end]==text), known labels,
and one shared schema_ver. Docs a run is missing/failed are reported as a gap,
never scored as zero.

    uv run python scripts/compare.py runs/opus-agent-r1 runs/anthropic-claude-sonnet-5
    uv run python scripts/compare.py runs/m-r1 runs/m-r2 runs/m-r3 --match relaxed --json out.json
"""
import sys, json, hashlib, argparse, pathlib, itertools, statistics

DATASET_DEFAULT = "datasets/mtsamples-ner-v1"
ENTITIES = ["Condition", "Intervention", "Investigation", "Result", "Drug_or_device", "Locus"]
MODIFIERS = ["Negation", "Laterality", "Sub_location"]
ENTITY_SET, MODIFIER_SET = set(ENTITIES), set(MODIFIERS)
LABELS = ENTITY_SET | MODIFIER_SET


def _die(msg):
    print(f"compare: {msg}", file=sys.stderr)
    sys.exit(2)


def load_manifest(dataset):
    rows = {}
    with open(pathlib.Path(dataset) / "manifest.jsonl") as f:
        for line in f:
            r = json.loads(line)
            rows[r["doc_id"]] = r
    return rows


def load_run(run_dir, manifest, dataset):
    """Load one run and CHECK it against the frozen dataset. Returns
    {name, meta, docs:{doc_id:{ents:[...], mods:[...]}}, failed:set, n_unlocated}.
    Each span kept as a dict with i/start/end/text/label(/modifies). Unlocated
    spans (start/end None) are dropped from scoring but counted."""
    run = pathlib.Path(run_dir)
    pred_path = run if run.is_file() else run / "predictions.jsonl"
    if not pred_path.exists():
        _die(f"no predictions.jsonl at {pred_path}")
    meta = {}
    meta_path = (run if run.is_dir() else run.parent) / "run.json"
    if meta_path.exists():
        meta = json.load(open(meta_path))
    name = run.name if run.is_dir() else run.stem

    docs, failed, n_unlocated = {}, set(), 0
    with open(pred_path) as f:
        for line in f:
            rec = json.loads(line)
            did = rec["doc_id"]
            if did not in manifest:
                _die(f"{name}: doc {did} not in dataset {dataset.name}")
            if "error" in rec and not rec.get("entities"):
                failed.add(did)                              # a failed doc: report as gap, don't score
                continue
            doc = (dataset / manifest[did]["text_file"]).read_text()
            if hashlib.sha256(doc.encode()).hexdigest() != manifest[did]["text_sha256"]:
                _die(f"{name}: {did} sha256 != manifest — run annotated different bytes, cannot compare")
            ents, mods = [], []
            for e in rec.get("entities", []):
                label = e.get("label")
                if label not in LABELS:
                    _die(f"{name}: {did} unknown label {label!r} (not in SCHEMA.md)")
                start, end, text = e.get("start"), e.get("end"), e.get("text", "")
                if start is None or end is None:            # unlocated: no offsets to compare
                    n_unlocated += 1
                    continue
                if not (isinstance(start, int) and isinstance(end, int) and 0 <= start <= end <= len(doc)):
                    _die(f"{name}: {did} i={e.get('i')} bad offsets [{start},{end})")
                if doc[start:end] != text:                  # offset sanity — a misaligned run is meaningless
                    _die(f"{name}: {did} i={e.get('i')} doc[{start}:{end}]={doc[start:end]!r} != text {text!r}")
                span = {"i": e.get("i"), "start": start, "end": end, "text": text, "label": label}
                if label in MODIFIER_SET:
                    span["modifies"] = e.get("modifies")     # index into THIS run's entity list
                    mods.append(span)
                else:
                    ents.append(span)
            docs[did] = {"ents": ents, "mods": mods}
    return {"name": name, "meta": meta, "docs": docs, "failed": failed, "n_unlocated": n_unlocated}


def compatible(a, b, match):
    if a["label"] != b["label"]:
        return False
    if match == "exact":
        return a["start"] == b["start"] and a["end"] == b["end"]
    return a["start"] < b["end"] and b["start"] < a["end"]    # relaxed: overlap


def match_spans(A, B, match):
    """Greedy one-to-one match between span lists A and B. Deterministic (both
    pre-sorted by offset). Returns list of (a, b) matched pairs."""
    A = sorted(A, key=lambda s: (s["start"], s["end"]))
    B = sorted(B, key=lambda s: (s["start"], s["end"]))
    used_b, pairs = set(), []
    for a in A:
        for j, b in enumerate(B):
            if j in used_b:
                continue
            if compatible(a, b, match):
                used_b.add(j); pairs.append((a, b)); break
    return pairs


def prf(tp, na, nb):
    """precision, recall, F1. F1 is symmetric (swapping A/B flips P and R only).
    Both empty => 1.0 (the runs agree: neither annotated anything)."""
    p = tp / na if na else (1.0 if nb == 0 else 0.0)
    r = tp / nb if nb else (1.0 if na == 0 else 0.0)
    f = (2 * tp / (na + nb)) if (na + nb) else 1.0
    return p, r, f


def score_pair(runA, runB, match):
    """Score run A vs run B over shared, scorable docs. Returns a result dict."""
    shared = sorted((set(runA["docs"]) | runA["failed"]) & (set(runB["docs"]) | runB["failed"]))
    scorable = [d for d in shared if d in runA["docs"] and d in runB["docs"]]
    gap = sorted(set(shared) - set(scorable))                 # present but failed in one run

    micro = {"tp": 0, "na": 0, "nb": 0}
    by_label = {L: {"tp": 0, "na": 0, "nb": 0} for L in ENTITIES}
    mod_micro = {"tp": 0, "na": 0, "nb": 0}
    mod_by_label = {L: {"tp": 0, "na": 0, "nb": 0} for L in MODIFIERS}
    per_doc_f1 = []

    for did in scorable:
        ea, eb = runA["docs"][did]["ents"], runB["docs"][did]["ents"]
        pairs = match_spans(ea, eb, match)
        # index -> matched partner index, for validating modifier targets
        a_to_b = {a["i"]: b["i"] for a, b in pairs}
        micro["tp"] += len(pairs); micro["na"] += len(ea); micro["nb"] += len(eb)
        _, _, f = prf(len(pairs), len(ea), len(eb))
        per_doc_f1.append(f)
        for L in ENTITIES:
            la = [s for s in ea if s["label"] == L]
            lb = [s for s in eb if s["label"] == L]
            tp = sum(1 for a, b in pairs if a["label"] == L)
            by_label[L]["tp"] += tp; by_label[L]["na"] += len(la); by_label[L]["nb"] += len(lb)

        # modifiers: separate pass, target entity must itself be a matched pair
        ma, mb = runA["docs"][did]["mods"], runB["docs"][did]["mods"]
        mpairs = []
        used = set()
        for a in sorted(ma, key=lambda s: (s["start"], s["end"])):
            for j, b in enumerate(sorted(mb, key=lambda s: (s["start"], s["end"]))):
                if j in used or not compatible(a, b, match):
                    continue
                if a.get("modifies") is not None and a_to_b.get(a["modifies"]) == b.get("modifies"):
                    used.add(j); mpairs.append((a, b)); break
        mod_micro["tp"] += len(mpairs); mod_micro["na"] += len(ma); mod_micro["nb"] += len(mb)
        for L in MODIFIERS:
            la = [s for s in ma if s["label"] == L]
            lb = [s for s in mb if s["label"] == L]
            tp = sum(1 for a, b in mpairs if a["label"] == L)
            mod_by_label[L]["tp"] += tp; mod_by_label[L]["na"] += len(la); mod_by_label[L]["nb"] += len(lb)

    p, r, f_micro = prf(micro["tp"], micro["na"], micro["nb"])
    f_macro = statistics.mean(per_doc_f1) if per_doc_f1 else 1.0
    return {
        "a": runA["name"], "b": runB["name"],
        "docs_scored": len(scorable), "gap": gap,
        "precision": p, "recall": r, "micro_f1": f_micro, "macro_f1": f_macro,
        "by_type": {L: prf(v["tp"], v["na"], v["nb"])[2] for L, v in by_label.items()},
        "spans": {"a": micro["na"], "b": micro["nb"], "matched": micro["tp"]},
        "modifiers_micro_f1": prf(mod_micro["tp"], mod_micro["na"], mod_micro["nb"])[2],
        "modifiers_by_type": {L: prf(v["tp"], v["na"], v["nb"])[2] for L, v in mod_by_label.items()},
    }


def spread(vals):
    return {
        "mean": statistics.mean(vals), "min": min(vals), "max": max(vals),
        "stdev": statistics.stdev(vals) if len(vals) > 1 else 0.0,
    }


def warn_config(runs):
    """Warn (do not stop) if config that must be held constant differs across runs.
    schema_ver mismatch is a hard stop handled by the caller; here we warn on the
    softer keys that make agreement across runs mean less."""
    for key in ("temperature", "prompt_ver", "reasoning_effort", "model"):
        vals = {r["name"]: r["meta"].get(key) for r in runs}
        if len(set(vals.values())) > 1:
            shown = ", ".join(f"{n}={v!r}" for n, v in vals.items())
            print(f"  WARN {key} differs across runs: {shown}")


def main():
    ap = argparse.ArgumentParser(description="Compare runs span-by-span over the frozen dataset.")
    ap.add_argument("runs", nargs="+", help="two or more run dirs (runs/<model>); >=3 for self-consistency")
    ap.add_argument("--dataset", default=DATASET_DEFAULT)
    ap.add_argument("--match", choices=["exact", "relaxed"], default="exact")
    ap.add_argument("--by-type", action="store_true", help="print the per-label block (also always in --json)")
    ap.add_argument("--json", help="write the full result object here")
    args = ap.parse_args()

    if len(args.runs) < 2:
        _die("need at least two runs to compare")

    dataset = pathlib.Path(args.dataset)
    manifest = load_manifest(dataset)
    runs = [load_run(r, manifest, dataset) for r in args.runs]

    # hard stop: agreement across schema versions is meaningless
    schemas = {r["name"]: r["meta"].get("schema_ver") for r in runs}
    if len({s for s in schemas.values() if s is not None}) > 1:
        _die(f"schema_ver differs across runs, refusing to compare: {schemas}")

    print(f"dataset: {dataset.name}   match: {args.match}   runs: {', '.join(r['name'] for r in runs)}")
    warn_config(runs)
    for r in runs:
        note = []
        if r["failed"]:
            note.append(f"{len(r['failed'])} failed docs")
        if r["n_unlocated"]:
            note.append(f"{r['n_unlocated']} unlocated spans dropped")
        print(f"  {r['name']}: {len(r['docs'])} docs scored" + (f"  ({'; '.join(note)})" if note else ""))
    print()

    pairs = list(itertools.combinations(range(len(runs)), 2))
    results = [score_pair(runs[i], runs[j], args.match) for i, j in pairs]

    key = f"{'exact' if args.match == 'exact' else 'relaxed'}"
    print(f"ENTITY F1 ({key} match)")
    print(f"  {'pair':<44}{'micro':>8}{'macro':>8}{'prec':>8}{'rec':>8}{'docs':>6}")
    for res in results:
        pair = f"{res['a']} | {res['b']}"
        print(f"  {pair:<44}{res['micro_f1']:>8.3f}{res['macro_f1']:>8.3f}"
              f"{res['precision']:>8.3f}{res['recall']:>8.3f}{res['docs_scored']:>6}")
        if res["gap"]:
            print(f"     gap (present but failed in one run): {', '.join(res['gap'])}")

    micro_f1s = [res["micro_f1"] for res in results]
    agg = spread(micro_f1s)
    label = "self-consistency" if len({r["meta"].get("model") for r in runs}) == 1 else "agreement"
    if len(results) > 1:
        print(f"\n{label} (mean pairwise micro-F1): {agg['mean']:.3f}  "
              f"[min {agg['min']:.3f}, max {agg['max']:.3f}, sd {agg['stdev']:.3f}]")

    # per-label: mean of the per-pair micro F1 for each label
    by_type = {L: statistics.mean([res["by_type"][L] for res in results]) for L in ENTITIES}
    mod_by_type = {L: statistics.mean([res["modifiers_by_type"][L] for res in results]) for L in MODIFIERS}
    mod_overall = statistics.mean([res["modifiers_micro_f1"] for res in results])
    # per-label always prints (the --by-type flag documents intent; spec: "prints anyway")
    print("\nby entity type (mean pairwise micro-F1)")
    for L in ENTITIES:
        print(f"  {L:<16}{by_type[L]:>8.3f}")
    print(f"\nmodifiers (separate pass): {mod_overall:.3f}")
    for L in MODIFIERS:
        print(f"  {L:<16}{mod_by_type[L]:>8.3f}")

    if args.json:
        out = {
            "dataset": dataset.name, "match": args.match,
            "runs": [r["name"] for r in runs],
            "pairwise": {f"{res['a']}|{res['b']}": {
                "micro_f1": res["micro_f1"], "macro_f1": res["macro_f1"],
                "precision": res["precision"], "recall": res["recall"],
                "docs_scored": res["docs_scored"], "gap": res["gap"],
                "spans": res["spans"], "by_type": res["by_type"],
                "modifiers_micro_f1": res["modifiers_micro_f1"],
                "modifiers_by_type": res["modifiers_by_type"],
            } for res in results},
            "aggregate_f1": agg,
            "aggregate_kind": label,
            "by_type": {L: {"mean_f1": by_type[L]} for L in ENTITIES},
            "modifiers": {"mean_f1": mod_overall,
                          "by_type": {L: {"mean_f1": mod_by_type[L]} for L in MODIFIERS}},
        }
        json.dump(out, open(args.json, "w"), indent=2)
        print(f"\nwrote {args.json}")


if __name__ == "__main__":
    main()
