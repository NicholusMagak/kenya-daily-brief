#!/usr/bin/env python3
"""Label stored articles for entity-scoped tone, per docs/SENTIMENT.md.

    python3 label.py              # label everything not yet attempted
    python3 label.py --limit 20
    python3 label.py --dry-run    # show the prompt for one article, call nothing

Requires ANTHROPIC_API_KEY in the environment.
"""

import argparse
import json
import os
import sys

import store

MODEL = "claude-opus-5"
LABELLER = "model"

# Must match the version header in docs/SENTIMENT.md. Labels carry it, and
# labels from different rubric versions are never compared.
RUBRIC_VERSION = "v1.0-headline-standfirst"

SUBJECT_TYPES = [
    "person",
    "organisation",
    "government_body",
    "party",
    "place",
    "company",
]

# The rubric, as prompt. Derived from docs/SENTIMENT.md — if that file changes,
# change this and bump RUBRIC_VERSION in both.
SYSTEM = """You label Kenyan news items for entity-scoped tone, following the \
definition below exactly. The definition overrides any general intuition you \
have about sentiment.

You see only a HEADLINE and a STANDFIRST (one to three sentences from the RSS \
feed). You never see the article body. Judge only what this text shows.

<definition>
tone is the stance the text, as written, takes toward a named entity: whether
its framing, word choice, and selection of detail leave a reasonable Kenyan
reader with a worse, unchanged, or better impression of that entity's conduct
or standing.

You are NOT scoring: whether the events described are good or bad; whether the
text is pleasant to read; the feelings of people quoted in it.

negative - the framing damages the entity: blame attributed, adverse finding
  reported as fact, critical characterisation in the text's own voice,
  unflattering detail foregrounded.
positive - the framing credits the entity: achievement reported as fact, praise
  in the text's own voice, favourable framing adopted without attribution.
neutral  - the text reports events and attributes evaluative claims to their
  sources without adopting a posture. Straight reportage is neutral even when
  the events are catastrophic. Most items are neutral.
</definition>

<rules>
R1 A negative event is not a negative tone unless the text attributes blame.
   "16 injured as protests force suspension of land registration" is negative
   toward nobody.
R2 Reported accusations are neutral toward BOTH parties. "Sifuna accuses Ruto
   of undermining devolution" is neutral toward Ruto and neutral toward Sifuna:
   the verb "accuses" carries the attribution. It becomes negative toward the
   accused only if the text asserts the charge as fact in its own voice.
R3 "charged with" / "under investigation" / "accused of" is neutral toward the
   accused. "convicted" / "found by the Auditor-General to have" is negative.
R4 Headline and standfirst are both the text. Where they conflict, follow the
   headline and cite it as evidence.
R5 If the text takes no posture toward an entity, OMIT it. Do not emit neutral
   rows for entities merely mentioned, named as a location, or appearing only
   as an attribution tag ("police say"). An item may legitimately produce zero
   labels.
R6 Attributed official claims are neutral ("Babu Owino vows to tackle garbage
   menace"). The same claims asserted in the text's own voice are positive
   ("the project will create 2,000 jobs").
R7 Judge Swahili and Sheng on Kenyan meaning, not English lexicon: maandamano
   (protests) is a neutral event descriptor; wash wash (fraud) is strongly
   negative; tanga tanga and kieleweke are neutral faction labels; hustler is
   in-group political self-identification, not an insult; mzee is respectful.
R8 In sport a loss is negative toward the loser, a win positive toward the
   winner. Obituaries are positive toward the deceased.
R9 Loaded characterisation in the text's own voice IS tone. "Ruto's Tata
   Chemicals tantrum spooks investors" is negative toward Ruto, because
   "tantrum" is the publication's word, not a quoted source's.
</rules>

<entity_selection>
Label a named entity (a proper noun - not "the government", not "residents")
only if the headline or standfirst makes an agentive or evaluative claim about
it: it acts, is acted upon, or is characterised. At most three, ranked
headline-first. Canonicalise names: "President Ruto" and "William Ruto" are one
subject, "William Ruto".
</entity_selection>

For each entity give tone, subject, subject_type, confidence, and evidence - a
verbatim span of at most 200 characters copied from the headline or standfirst
that supports the tone. If no span supports a non-neutral reading, the tone is
neutral.

confidence is your probability that a second careful reader applying this
definition returns the same tone. Be calibrated: use the full range, and go
below 0.5 where the framing is mixed or the standfirst is too thin to support a
confident call."""

SCHEMA = {
    "type": "object",
    "properties": {
        "labels": {
            "type": "array",
            "maxItems": 3,
            "items": {
                "type": "object",
                "properties": {
                    "subject": {"type": "string"},
                    "subject_type": {"type": "string", "enum": SUBJECT_TYPES},
                    "tone": {
                        "type": "string",
                        "enum": ["negative", "neutral", "positive"],
                    },
                    "confidence": {"type": "number"},
                    "evidence": {"type": "string"},
                },
                "required": [
                    "subject",
                    "subject_type",
                    "tone",
                    "confidence",
                    "evidence",
                ],
                "additionalProperties": False,
            },
        }
    },
    "required": ["labels"],
    "additionalProperties": False,
}


def user_message(article):
    return (
        f"HEADLINE: {article['title']}\n\n"
        f"STANDFIRST: {article['standfirst']}\n\n"
        f"(Source: {article['source']} - {article['category']})"
    )


def label_article(client, article):
    """Returns (labels, status, detail). Never raises on an API-level problem."""
    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=16000,
            thinking={"type": "adaptive"},
            system=[
                {
                    "type": "text",
                    "text": SYSTEM,
                    "cache_control": {"type": "ephemeral"},
                }
            ],
            messages=[{"role": "user", "content": user_message(article)}],
            output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
        )
    except Exception as error:
        return [], "error", f"{type(error).__name__}: {error}"

    # Safety classifiers can decline: HTTP 200, stop_reason "refusal", no
    # usable content. Political reporting is exactly the shape that can trip
    # this, and unhandled it looks like an article with no entities rather
    # than an article we failed to label.
    if response.stop_reason == "refusal":
        detail = ""
        if getattr(response, "stop_details", None):
            detail = getattr(response.stop_details, "category", "") or ""
        return [], "refused", detail

    try:
        text = next(b.text for b in response.content if b.type == "text")
        labels = json.loads(text)["labels"]
    except (StopIteration, KeyError, json.JSONDecodeError) as error:
        return [], "error", f"unparseable response: {error}"

    return labels, "ok", ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = store.connect()
    pending = store.unlabelled(conn, LABELLER, limit=args.limit)

    if not pending:
        print("nothing to label")
        return

    if args.dry_run:
        print("=== SYSTEM ===")
        print(SYSTEM)
        print("\n=== USER (first pending article) ===")
        print(user_message(pending[0]))
        print(f"\n{len(pending)} article(s) pending. No API call made.")
        return

    if not os.environ.get("ANTHROPIC_API_KEY"):
        sys.exit("ANTHROPIC_API_KEY is not set")

    import anthropic

    client = anthropic.Anthropic()

    counts = {"ok": 0, "refused": 0, "error": 0}
    total_labels = 0

    for article in pending:
        labels, status, detail = label_article(client, article)
        counts[status] = counts.get(status, 0) + 1

        if status == "ok":
            store.save_labels(conn, article["id"], labels, LABELLER, RUBRIC_VERSION)
            total_labels += len(labels)
        else:
            print(f"  {status}: {article['title'][:60]} - {detail}", file=sys.stderr)

        store.record_run(conn, article["id"], LABELLER, status, detail)
        conn.commit()

    print(
        f"labelled {counts['ok']} article(s) -> {total_labels} (article, entity) pairs"
    )
    if counts["refused"]:
        print(f"refused: {counts['refused']}")
    if counts["error"]:
        print(f"errors:  {counts['error']}")
    conn.close()


if __name__ == "__main__":
    main()
