#!/usr/bin/env python3
"""Blind hand-check of model labels against your own judgement.

    python3 handcheck.py              # adjudicate 50 pairs, resumable
    python3 handcheck.py --n 30
    python3 handcheck.py --status

You are shown the headline, the standfirst, and the entity. You are NOT shown
the model's tone, confidence, or evidence — that is the point. Reading the
prediction first turns the exercise into agreeing with it, and the number stops
meaning anything.

The entity is given rather than re-selected, because the quantity being measured
is tone agreement. Entity-selection disagreement is reported separately by
agreement.py.

Judge against docs/SENTIMENT.md. Keep it open.
"""

import argparse
import sys
import textwrap

import store

LABELLER = "human"
MODEL_LABELLER = "model"
RUBRIC_VERSION = "v1.0-headline-standfirst"

KEYS = {"1": "negative", "2": "neutral", "3": "positive"}

REMINDER = """\
  1 negative   the framing damages them (blame attributed, adverse finding as
               fact, loaded characterisation in the paper's own voice)
  2 neutral    reportage; evaluative claims attributed to sources. An accusation
               reported as an accusation is NEUTRAL toward both parties.
  3 positive   the framing credits them (achievement as fact, praise in the
               paper's own voice)
  s skip       cannot decide from this text
  q quit       save and stop (resumable)"""


def wrap(text, width=76, indent="  "):
    return "\n".join(
        textwrap.fill(line, width=width, initial_indent=indent,
                      subsequent_indent=indent)
        for line in text.splitlines() or [""]
    )


def show_status(conn):
    model_n = len(store.labels_for(conn, MODEL_LABELLER))
    human_n = len(store.labels_for(conn, LABELLER))
    counts = store.tone_counts(conn, MODEL_LABELLER)
    print(f"\nmodel labels:  {model_n}")
    print(f"human labels:  {human_n}")
    if counts:
        print("model tone distribution:")
        total = sum(counts.values())
        for tone in store.TONES:
            n = counts.get(tone, 0)
            print(f"  {tone:<9} {n:>5}  {n / total:>6.1%}")
    print()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=50, help="pairs to adjudicate")
    parser.add_argument("--seed", default="handcheck-1",
                        help="change only to draw a different sample")
    parser.add_argument("--status", action="store_true")
    args = parser.parse_args()

    conn = store.connect()

    if args.status:
        show_status(conn)
        return

    if not store.labels_for(conn, MODEL_LABELLER):
        sys.exit("No model labels yet. Run label.py first.")

    per_class = max(1, args.n // len(store.TONES))
    sample = store.stratified_sample(
        conn, MODEL_LABELLER, per_class, args.seed, exclude_labeller=LABELLER
    )

    if not sample:
        print("Nothing left to adjudicate for this seed — sample complete.")
        print("Next: python3 store.py export && python3 docs/agreement.py "
              "model_labels.csv human_labels.csv --corpus corpus_labels.csv")
        return

    done_before = len(store.labels_for(conn, LABELLER))

    print(f"\n{len(sample)} pair(s) to adjudicate "
          f"(stratified, {per_class} per predicted tone).")
    print("The model's answer is hidden. Judge from docs/SENTIMENT.md.\n")
    print(REMINDER)

    recorded = 0
    for i, (aid, subject, _predicted) in enumerate(sample, start=1):
        article = conn.execute(
            "SELECT * FROM articles WHERE id = ?", (aid,)
        ).fetchone()

        print("\n" + "=" * 78)
        print(f"[{i}/{len(sample)}]  {article['source']}  ·  {article['category']}")
        print("-" * 78)
        print(wrap(article["title"]))
        print()
        print(wrap(article["standfirst"]))
        print("-" * 78)
        print(f"  TONE TOWARD:  {subject}")
        print("=" * 78)

        choice = ""
        while choice not in list(KEYS) + ["s", "q"]:
            try:
                choice = input("  1 neg / 2 neu / 3 pos / s skip / q quit > ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                choice = "q"
                print()
            if choice == "?":
                print(REMINDER)
                choice = ""

        if choice == "q":
            break
        if choice == "s":
            continue

        store.upsert_label(
            conn,
            aid,
            {"subject": subject, "tone": KEYS[choice], "subject_type": "unknown",
             "confidence": None, "evidence": ""},
            LABELLER,
            RUBRIC_VERSION,
        )
        conn.commit()
        recorded += 1

    total = len(store.labels_for(conn, LABELLER))
    print(f"\nrecorded {recorded} this session · {total} human labels total "
          f"(was {done_before})")

    if total >= args.n:
        print("\nSample complete. Now:")
        print("  python3 store.py export")
        print("  python3 docs/agreement.py model_labels.csv human_labels.csv "
              "--corpus corpus_labels.csv")
    else:
        print(f"\n{args.n - total} to go — re-run handcheck.py to continue "
              "(same seed resumes the same sample).")
    conn.close()


if __name__ == "__main__":
    main()
