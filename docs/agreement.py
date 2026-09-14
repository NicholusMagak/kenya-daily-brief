#!/usr/bin/env python3
"""Score LLM sentiment labels against blind human adjudication.

Usage:
    python agreement.py model_labels.csv human_labels.csv
    python agreement.py model_labels.csv human_labels.csv --corpus all_model_labels.csv

Both CSVs need the columns: article_id, subject, tone
The model CSV may also carry `confidence`, which enables the calibration table.

Rows are joined on (article_id, subject). Pairs present in only one file are
reported and excluded — usually they mean the two sides disagreed about entity
selection (rubric R5), which is worth knowing about separately.

--corpus takes the model's labels for the WHOLE corpus, not just the sample. The
hand-check sample is stratified by predicted tone, so raw agreement over it is
not corpus agreement; given the corpus this re-weights per-stratum agreement by
the true class prior. That re-weighted figure is the one to put in the README.

Stdlib only.
"""

import argparse
import csv
import sys
from collections import Counter, defaultdict

TONES = ["negative", "neutral", "positive"]


def load(path, need_confidence=False):
    rows = {}
    with open(path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        missing = {"article_id", "subject", "tone"} - set(reader.fieldnames or [])
        if missing:
            sys.exit(f"{path}: missing column(s): {', '.join(sorted(missing))}")
        for i, row in enumerate(reader, start=2):
            tone = row["tone"].strip().lower()
            if tone not in TONES:
                sys.exit(f"{path}:{i}: tone must be one of {TONES}, got {tone!r}")
            key = (row["article_id"].strip(), row["subject"].strip())
            if key in rows:
                sys.exit(f"{path}:{i}: duplicate pair {key}")
            conf = None
            if need_confidence and row.get("confidence"):
                try:
                    conf = float(row["confidence"])
                except ValueError:
                    sys.exit(f"{path}:{i}: confidence must be a float")
            rows[key] = (tone, conf)
    return rows


def kappa(pairs):
    """Cohen's kappa. pairs is a list of (model_tone, human_tone)."""
    n = len(pairs)
    po = sum(m == h for m, h in pairs) / n
    m_counts = Counter(m for m, _ in pairs)
    h_counts = Counter(h for _, h in pairs)
    pe = sum((m_counts[t] / n) * (h_counts[t] / n) for t in TONES)
    return (po - pe) / (1 - pe) if pe < 1 else float("nan")


def bar(pct, width=24):
    filled = round(pct / 100 * width)
    return "#" * filled + "." * (width - filled)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("model")
    ap.add_argument("human")
    ap.add_argument("--corpus", help="model labels for the full corpus, for prior re-weighting")
    args = ap.parse_args()

    model = load(args.model, need_confidence=True)
    human = load(args.human)

    only_model = set(model) - set(human)
    only_human = set(human) - set(model)
    shared = sorted(set(model) & set(human))
    if not shared:
        sys.exit("No overlapping (article_id, subject) pairs. Check the keys match.")

    pairs = [(model[k][0], human[k][0]) for k in shared]
    n = len(pairs)
    agree = sum(m == h for m, h in pairs)
    po = agree / n

    print(f"\nPairs adjudicated:  {n}")
    print(f"Raw agreement:      {po:.1%}  ({agree}/{n})")
    print(f"Cohen's kappa:      {kappa(pairs):.3f}")

    if only_model or only_human:
        print(
            f"\nEntity-selection mismatch (excluded): "
            f"{len(only_model)} model-only, {len(only_human)} human-only"
        )
        for k in sorted(only_model)[:5]:
            print(f"  model only:  {k[0]}  {k[1]}")
        for k in sorted(only_human)[:5]:
            print(f"  human only:  {k[0]}  {k[1]}")

    # Confusion matrix, human as reference.
    print("\nConfusion matrix (rows = model, cols = human)")
    cm = Counter(pairs)
    head = "".join(f"{t[:8]:>10}" for t in TONES)
    print(f"{'':>10}{head}{'total':>10}")
    for m in TONES:
        cells = "".join(f"{cm[(m, h)]:>10}" for h in TONES)
        print(f"{m:>10}{cells}{sum(cm[(m, h)] for h in TONES):>10}")
    totals = "".join(f"{sum(cm[(m, h)] for m in TONES):>10}" for h in TONES)
    print(f"{'total':>10}{totals}{n:>10}")

    # Per predicted class — these are the strata.
    print("\nAgreement by predicted tone (the sampling strata)")
    strata = {}
    for t in TONES:
        sub = [(m, h) for m, h in pairs if m == t]
        if not sub:
            print(f"  {t:<9} no sampled pairs")
            continue
        rate = sum(m == h for m, h in sub) / len(sub)
        strata[t] = rate
        print(f"  {t:<9} {rate:>6.1%}  (n={len(sub):>3})  {bar(rate * 100)}")

    # Calibration: does confidence mean anything?
    conf_bands = [(0.9, 1.01, "conf >= 0.9"), (0.7, 0.9, "conf 0.7-0.9"),
                  (0.5, 0.7, "conf 0.5-0.7"), (0.0, 0.5, "conf < 0.5")]
    have_conf = [k for k in shared if model[k][1] is not None]
    if have_conf:
        print("\nAgreement by confidence band (is confidence calibrated?)")
        for lo, hi, label in conf_bands:
            sub = [(model[k][0], human[k][0]) for k in have_conf if lo <= model[k][1] < hi]
            if not sub:
                print(f"  {label:<14} —")
                continue
            rate = sum(m == h for m, h in sub) / len(sub)
            print(f"  {label:<14} {rate:>6.1%}  (n={len(sub):>3})  {bar(rate * 100)}")
        print("  If these are flat, confidence is decoration: fix it or drop the field.")

    # Prior re-weighting.
    if args.corpus:
        corpus = load(args.corpus)
        prior = Counter(t for t, _ in corpus.values())
        total = sum(prior.values())
        covered = [t for t in TONES if t in strata]
        mass = sum(prior[t] for t in covered)
        if mass == 0:
            print("\nCorpus has no labels in the sampled strata; skipping re-weighting.")
        else:
            weighted = sum(strata[t] * prior[t] / mass for t in covered)
            print(f"\nCorpus prior (n={total}):")
            for t in TONES:
                print(f"  {t:<9} {prior[t] / total:>6.1%}")
            if mass < total:
                print(f"  note: {1 - mass / total:.1%} of corpus falls in unsampled strata")
            print(f"\nPrior-weighted agreement: {weighted:.1%}   <- report this one")
    else:
        print("\nNo --corpus given: the raw rate above is the stratified-sample rate,")
        print("which overstates corpus performance if rare classes were oversampled.")

    # Disagreements, so the write-up can say something about direction.
    disagreements = [(k, model[k][0], human[k][0]) for k in shared if model[k][0] != human[k][0]]
    if disagreements:
        print(f"\nDisagreements ({len(disagreements)}):")
        by_dir = defaultdict(int)
        for k, m, h in disagreements:
            by_dir[(m, h)] += 1
            conf = model[k][1]
            conf_s = f"  conf={conf:.2f}" if conf is not None else ""
            print(f"  {k[0]:<16} {k[1]:<28} model={m:<9} human={h:<9}{conf_s}")
        print("\n  Direction:")
        for (m, h), c in sorted(by_dir.items(), key=lambda x: -x[1]):
            print(f"    model {m} -> human {h}: {c}")

    print()


if __name__ == "__main__":
    main()
