#!/usr/bin/env python3
"""Build the mtsamples-ner-v1 dataset.

Pipeline: load MTSamples CSV -> clean (drop empty/stub, strip appended
keyword tail) -> derive note_type by header rules -> two-axis stratified
random draw (specialty @ >=2% threshold + 'Other'  x  note_type), guarding
BOTH axis counters on every draw (CLEF marginal-matching, Roberts 2008) ->
write docs/*.txt + manifest.jsonl + sampling.json.

Deterministic: fixed SEED. Re-running reproduces the identical dataset.
"""
import csv, json, math, hashlib, random, re, argparse, collections, pathlib

CSV_DEFAULT = "/Users/husongtao/Projects/semantic-annotation-of-clinical-text/data/mtsamples/mtsamples.csv"
OUT_DEFAULT = "/Users/husongtao/Projects/clinical-annotation-tools/datasets/mtsamples-ner-v1"
N = 80
SEED = 20260723
SPECIALTY_THRESHOLD = 0.02   # keep as own stratum if share >= 2%, else 'Other'
NOTE_TYPE_FLOOR = 1          # every note_type gets at least this many
MIN_CHARS = 100              # drop stubs shorter than this (after cleaning)

SPECIALTY = {  # decoded from note content; see project notes
 '25':'Surgery','13':'Consult - History and Phy.','33':'Cardiovascular / Pulmonary',
 '9':'Orthopedic','15':'Radiology','36':'General Medicine','23':'Gastroenterology',
 '6':'Neurology','34':'SOAP / Chart / Progress Notes','38':'Obstetrics / Gynecology',
 '21':'Urology','4':'Discharge Summary','22':'ENT - Otolaryngology','28':'Neurosurgery',
 '39':'Hematology - Oncology','27':'Ophthalmology','30':'Nephrology','29':'Emergency Room Reports',
 '3':'Pediatrics - Neonatal','0':'Pain Management','12':'Psychiatry / Psychology',
 '32':'Office Notes','2':'Podiatry','14':'Dermatology','5':'Cosmetic / Plastic Surgery',
 '10':'Dentistry','24':'Letters','17':'Physical Medicine - Rehab','18':'Sleep Medicine',
 '7':'Endocrinology','26':'Bariatrics','37':'IME-QME-Work Comp etc.','1':'Chiropractic',
 '8':'Rheumatology','20':'Diets and Nutritions','16':'Speech - Language',
 '31':'Lab Medicine - Pathology','35':'Autopsy','11':'Allergy / Immunology',
 '19':'Hospice - Palliative Care'}

OTHER = "Other (rare specialties <2%)"


# ---------- cleaning ----------
def strip_keyword_tail(text):
    """Remove the lowercase, comma-separated keyword list appended to the
    end of most MTSamples notes (the original `keywords` column, glued on
    with no separator). Conservative: only strips a clear trailing run of
    >=4 all-lowercase, period-free, short segments."""
    toks = text.split(',')
    def kwlike(s):
        s = s.strip()
        if not s or '.' in s:                 return False
        if any(c.isupper() for c in s):       return False
        if len(s.split()) > 10:               return False
        if not re.search(r'[a-z]', s):        return False
        return True
    # drop trailing empty/whitespace segments (keyword lists often end in ", ")
    while toks and toks[-1].strip() == '':
        toks.pop()
    i = len(toks)
    while i > 0 and kwlike(toks[i-1]):
        i -= 1
    n_kw = len(toks) - i
    if n_kw < 4:
        return text, False
    boundary = toks[i-1] if i > 0 else ''
    m = re.search(r'\.\s*([a-z][a-z /&-]*)$', boundary)  # "...prose.specialtyword"
    if m:
        kept = toks[:i-1] + [boundary[:m.start()+1]]
    else:
        kept = toks[:i]
    body = ','.join(kept).strip()
    # keyword-dominated stubs strip down to near-nothing; let MIN_CHARS drop them
    return body, True


# ---------- note type (header rules v1) ----------
def note_type(t):
    h = t.upper(); head = h[:800]
    def has(*ks): return any(k in h for k in ks)
    if has('PREOPERATIVE DIAGNOS','POSTOPERATIVE DIAGNOS','OPERATION PERFORMED',
           'PROCEDURE PERFORMED','TITLE OF PROCEDURE','OPERATIVE NOTE','OPERATIVE PROCEDURE'):
        return 'Operative/Procedure'
    if has('GROSS DESCRIPTION','MICROSCOPIC DESCRIPTION','FROZEN SECTION') or 'EXTERNAL EXAMINATION' in h:
        return 'Pathology/Autopsy'
    if ('IMPRESSION:' in h or 'FINDINGS:' in h) and has('EXAM:','TECHNIQUE:','EXAMINATION:') and 'SUBJECTIVE' not in head:
        return 'Diagnostic report'
    if 'SUBJECTIVE:' in head and 'OBJECTIVE:' in h:
        return 'SOAP/Progress'
    if has('DISCHARGE DIAGNOS','HOSPITAL COURSE','ADMISSION DIAGNOS'):
        return 'Discharge summary'
    if has('CHIEF COMPLAINT','HISTORY OF PRESENT ILLNESS','REVIEW OF SYSTEMS','PHYSICAL EXAMINATION'):
        return 'Consult/H&P'
    return 'Other/Letter'
NOTE_TYPE_METHOD = "header-rules-v1"


# ---------- marginals (largest remainder, with floor) ----------
def allocate(counts, total, floor=0):
    keys = list(counts.keys())
    s = sum(counts.values())
    raw = {k: total * counts[k] / s for k in keys}
    base = {k: max(floor, int(math.floor(raw[k]))) for k in keys}
    # trim or add to hit `total` exactly
    diff = total - sum(base.values())
    if diff > 0:  # add to largest fractional remainders
        for k in sorted(keys, key=lambda k: -(raw[k]-math.floor(raw[k])))[:diff]:
            base[k] += 1
    elif diff < 0:  # remove from biggest buckets that stay >= floor
        for k in sorted(keys, key=lambda k: -base[k]):
            while diff < 0 and base[k] > floor:
                base[k] -= 1; diff += 1
            if diff == 0: break
    return base


# ---------- two-axis guarded draw ----------
def draw(pool, spec_target, nt_target, seed, spec_supply, nt_supply):
    """Guard both axis counters on every draw (CLEF marginal-matching). To
    avoid an endgame stall — a rare cell whose shared bucket fills first —
    consider the globally rarest note-type/specialty first, so scarce combos
    claim their slots before common ones exhaust the shared buckets.
    Randomness is preserved within each rarity tier (stable sort of a shuffle)."""
    rng = random.Random(seed)
    order = pool[:]; rng.shuffle(order)
    order.sort(key=lambda r: (nt_supply[r['_note_type']], spec_supply[r['_spec_bucket']]))
    spec_have = collections.Counter(); nt_have = collections.Counter()
    picked = []
    for r in order:
        if len(picked) == N: break
        s, nt = r['_spec_bucket'], r['_note_type']
        if spec_have[s] < spec_target[s] and nt_have[nt] < nt_target[nt]:
            picked.append(r); spec_have[s] += 1; nt_have[nt] += 1
    return picked, spec_have, nt_have


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--csv', default=CSV_DEFAULT)
    ap.add_argument('--out', default=OUT_DEFAULT)
    ap.add_argument('--report-only', action='store_true')
    args = ap.parse_args()
    csv.field_size_limit(10**7)

    rows = list(csv.DictReader(open(args.csv)))
    # clean
    universe = []
    for r in rows:
        raw = r['text'].strip()
        if not raw or raw.lower() == 'nan':
            continue
        body, stripped = strip_keyword_tail(raw)
        body = body.strip()
        if len(body) < MIN_CHARS or body.lower() == 'nan':
            continue
        code = r['label']
        spec = SPECIALTY.get(code, code)
        r['_clean'] = body
        r['_orig_len'] = len(raw)
        r['_stripped'] = stripped
        r['_spec_name'] = spec
        r['_note_type'] = note_type(body)
        universe.append(r)

    # specialty buckets @ threshold
    spec_counts = collections.Counter(r['_spec_name'] for r in universe)
    total = len(universe)
    keep = {s for s, c in spec_counts.items() if c/total >= SPECIALTY_THRESHOLD}
    for r in universe:
        r['_spec_bucket'] = r['_spec_name'] if r['_spec_name'] in keep else OTHER
    bucket_counts = collections.Counter(r['_spec_bucket'] for r in universe)
    nt_counts = collections.Counter(r['_note_type'] for r in universe)

    spec_target = allocate(bucket_counts, N, floor=0)
    nt_target   = allocate(nt_counts,   N, floor=NOTE_TYPE_FLOOR)

    picked, spec_have, nt_have = draw(universe, spec_target, nt_target, SEED,
                                      bucket_counts, nt_counts)

    print(f"clean universe: {total} of {len(rows)}")
    print(f"specialty buckets (>= {SPECIALTY_THRESHOLD:.0%}): {len(keep)} + Other = {len(bucket_counts)}")
    print(f"keyword-tail stripped: {sum(r['_stripped'] for r in universe)} notes")
    print(f"\n== specialty axis ==   target / got")
    for k in sorted(spec_target, key=lambda k:-spec_target[k]):
        print(f"  {k:34s} {spec_target[k]:2d} / {spec_have[k]:2d}")
    print(f"\n== note-type axis ==   target / got")
    for k in sorted(nt_target, key=lambda k:-nt_target[k]):
        print(f"  {k:22s} {nt_target[k]:2d} / {nt_have[k]:2d}")
    print(f"\nselected: {len(picked)} / {N}")
    if len(picked) != N:
        print("!! WARNING: draw stalled before N (joint sparsity). Inspect before use.")

    if args.report_only:
        return

    # write dataset
    out = pathlib.Path(args.out); (out/'docs').mkdir(parents=True, exist_ok=True)
    for stale in (out/'docs').glob('*.txt'):   # clear prior run
        stale.unlink()
    picked.sort(key=lambda r: int(r['id']))
    manifest = []
    for n, r in enumerate(picked, 1):
        doc_id = f"{n:04d}"
        text = r['_clean']
        (out/'docs'/f"{doc_id}.txt").write_text(text)
        manifest.append({
            "doc_id": doc_id,
            "source_id": r['id'],
            "specialty_code": r['label'],
            "specialty": r['_spec_name'],
            "specialty_bucket": r['_spec_bucket'],
            "note_type": r['_note_type'],
            "note_type_method": NOTE_TYPE_METHOD,
            "split": r['split'],
            "char_len": len(text),
            "orig_char_len": r['_orig_len'],
            "keyword_tail_stripped": r['_stripped'],
            "text_sha256": hashlib.sha256(text.encode()).hexdigest(),
            "text_file": f"docs/{doc_id}.txt",
        })
    with open(out/'manifest.jsonl', 'w') as f:
        for m in manifest:
            f.write(json.dumps(m) + "\n")
    sampling = {
        "dataset": "mtsamples-ner-v1",
        "source_csv": args.csv,
        "seed": SEED, "N": N,
        "clean_universe": total,
        "cleaning": {"min_chars": MIN_CHARS, "drop_empty_and_nan": True,
                     "keyword_tail_stripped_notes": sum(r['_stripped'] for r in universe)},
        "axes": {
            "specialty": {"threshold": SPECIALTY_THRESHOLD, "buckets": dict(bucket_counts),
                          "target": spec_target, "achieved": dict(spec_have)},
            "note_type": {"method": NOTE_TYPE_METHOD, "floor": NOTE_TYPE_FLOOR,
                          "counts": dict(nt_counts), "target": nt_target, "achieved": dict(nt_have)},
        },
        "method": "CLEF marginal-matching, guard both axis counters on every draw (Roberts 2008)",
    }
    json.dump(sampling, open(out/'sampling.json', 'w'), indent=2)
    print(f"\nwrote {len(manifest)} docs + manifest.jsonl + sampling.json to {out}")


if __name__ == "__main__":
    main()
