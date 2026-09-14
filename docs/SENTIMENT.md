# Sentiment label definition

This document defines the label. It is the specification the LLM labeller is
prompted from and the rubric the human adjudicator scores against. If the two
ever disagree about what a label *means*, this file wins and both get re-run.

## 1. The unit of analysis

**The unit is the `(article, entity)` pair, not the article.**

A Kenyan news article routinely praises one actor and condemns another inside a
single paragraph — a governor's defence and the auditor's findings, a party's
statement and the rival's rebuttal. A document-level score averages those into a
neutral that describes nothing. So we never label "the article". We label the
article's posture toward one named entity at a time, and an article with four
salient entities produces four rows.

## 2. The definition we chose

> **`tone` is the stance the article, as written, takes toward a named entity:
> whether its framing, word choice, and selection of detail leave a reasonable
> Kenyan reader with a worse, unchanged, or better impression of that entity's
> conduct or standing.**

The judgement is about *the text's posture*, which is observable in the prose,
and not about anything downstream of it.

Four things this deliberately excludes:

| Not this | Why |
|---|---|
| **Reader-facing positivity** ("is this pleasant to read") | Unmeasurable and useless. A well-written corruption exposé is unpleasant and excellent. |
| **Event valence** ("is the described thing bad") | A matatu crash is a bad event with no target. Only blame attribution makes it negative *toward someone*. See R1. |
| **The sentiment of quoted speakers** | An article reporting that A insulted B is not the article being negative toward B. See R2. |
| **The article's overall mood** | Mood is a property of a document; we are labelling a directed relation. |

## 3. Schema

One record per `(article, entity)` pair:

```json
{
  "article_id":   "str      — stable id from the ingest layer",
  "subject":      "str      — the entity as canonically named",
  "subject_type": "person | organisation | government_body | party | place | company",
  "tone":         "negative | neutral | positive",
  "confidence":   "float    — 0.0–1.0, see §6",
  "evidence":     "str      — a verbatim span from the article, ≤200 chars"
}
```

`evidence` is **required**, and it earns its place: it forces the labeller to
point at text rather than at a vibe, it makes a human check take fifteen seconds
instead of a full re-read, and where the span doesn't support the tone you have
found a bad label without needing to re-adjudicate the article.

## 4. The three classes

**negative** — the article's framing damages the entity. Blame is attributed, an
adverse finding is reported as fact, the entity's conduct is characterised
critically by the article's own voice, or unflattering detail is selected and
foregrounded without counterweight.

**positive** — the article's framing credits the entity. Achievement is reported
as fact, praise appears in the article's own voice, or favourable framing is
adopted without attribution.

**neutral** — defined positively, not as a leftover bucket. The article reports
what happened and what people said about the entity, attributing evaluative
claims to their sources, without adopting a posture of its own. Straight
reportage is neutral *even when the events are catastrophic*. Most of the corpus
should land here; a neutral rate below ~50% is a signal the labeller has drifted
into scoring event valence.

## 5. Decision rules

These exist because the edge cases are the whole difficulty, and an unwritten
rule is one the human adjudicator will apply differently on Tuesday than the
model applied on Monday.

**R1 — Event valence is not tone.** "Floods displace 400 in Tana River" is
negative toward nobody. It becomes negative toward the county government only if
the article frames them as culpable ("despite a drainage budget approved three
years ago").

**R2 — Quoted attacks are neutral by default.** If the article reports that A
accused B, tone toward B is **neutral** — clean attribution is the article doing
its job. It flips to **negative** only where the article amplifies: repeats the
charge in its own voice, gives it the headline without attribution, stacks
sources on one side, or omits an obviously available response.

**R3 — Accusation is not finding.** "Charged with", "under investigation",
"summoned by EACC" → **neutral** toward the accused; the article is reporting a
process. "Convicted", "found by the Auditor-General to have", "ordered to repay"
→ **negative**; an adverse fact is being reported.

**R4 — Headline framing counts, and counts double.** The headline is part of the
article and is where Kenyan framing concentrates. Where headline and body
diverge, label the article's overall posture but treat the headline as the
heaviest single piece of evidence, and say so in `evidence`.

**R5 — Mere mention produces no row.** An entity named only in passing — cited
for context, listed among attendees, named as a location — is not labelled at
all. See §7 for the selection test. Do not emit `neutral` rows for entities the
article has no posture toward; that inflates the neutral class and flatters the
agreement number.

**R6 — Press-release journalism.** A large share of Kenyan coverage reproduces
official statements. If evaluative content is attributed ("the ministry said the
project would create 2,000 jobs") → **neutral**. If the article adopts the claim
in its own voice ("the project will create 2,000 jobs") → **positive**; the text
has taken on the framing regardless of where it came from.

**R7 — Code-switching and Sheng are labelled on meaning, not on lexicon.** Judge
the Swahili or Sheng span for what it means in Kenyan usage. `maandamano`
(protests) is a neutral descriptor of an event, not a negative word. `wash wash`
(fraud) is strongly negative toward whoever it is attached to. Faction labels
like `tanga tanga` are neutral descriptors. `hustler` is in-group political
self-identification, not an insult. Where a term is genuinely contested, lower
`confidence` rather than guessing the tone.

**R8 — Sport and obituary.** A defeat is negative toward the losing side and a
win positive toward the winner; this is the one place event valence and tone
legitimately coincide, because the article's subject *is* the entity's
performance. Obituaries and tributes are positive toward the deceased.

**R9 — Satire and opinion columns.** Label the posture the piece actually takes,
not its literal surface. Where a piece is ironic and the direction is genuinely
ambiguous, `confidence ≤ 0.5`.

## 6. Confidence

The labeller's own probability that a second careful reader applying this
document would return the same `tone`.

| Band | Meaning |
|---|---|
| 0.9–1.0 | Explicit and unambiguous; the evidence span settles it alone. |
| 0.7–0.9 | Clear on a full read; a hurried reader might differ. |
| 0.5–0.7 | Genuinely mixed framing, or the call turns on one contested rule. |
| < 0.5 | Coin-flip. Surface for human review rather than shipping. |

Confidence is only worth having if it is calibrated, so the hand-check in §7
reports agreement **split by confidence band**. If agreement in the 0.9+ band is
not clearly higher than in the 0.5–0.7 band, the field is decoration and should
either be fixed or dropped from the schema.

## 7. Entity selection

An entity is labelled if it is a **named** entity (proper noun; not "the
government", not "residents") **and** at least one of:

- it appears in the headline or the first two paragraphs; **or**
- it is the subject or object of a main-clause predicate at least twice.

Cap at five entities per article, ranked by the above. Canonicalise before
labelling — `William Ruto` / `President Ruto` / `the President` collapse to one
subject string — because entity-scoped labels are worthless if the same person
appears under three keys.

## 8. Annotation and agreement protocol

The agreement number is the deliverable. It only means anything if the procedure
protects it:

1. **Sample 50 `(article, entity)` pairs**, stratified by *model-predicted* tone
   so the rare classes are actually represented. Random sampling of a corpus
   this neutral-heavy would return ~40 neutrals and measure nothing.
2. **Adjudicate blind.** The human labels from the article and this document
   with the model's output hidden. Reading the prediction first turns the
   exercise into agreeing with it — this single step is the difference between a
   real number and a flattering one.
3. **Freeze this document before adjudicating.** If a rule has to be added
   mid-check, note it, finish, then re-run both sides. A rubric edited during
   scoring measures nothing.
4. **Report** raw agreement, Cohen's κ, the 3×3 confusion matrix, per-class
   agreement, and agreement by confidence band.

**Report κ alongside raw agreement, not instead of it.** On a three-class task
with a dominant neutral, a labeller that answered "neutral" every time would
score somewhere near 60% raw. κ corrects for that agreement-by-chance, so the
pair of numbers is honest where either alone is not. And because the sample is
stratified, sample-level agreement is not corpus-level agreement — re-weight by
the corpus class prior for the headline figure (`agreement.py` does this when
given the full label file).

## 9. Known limits of this definition

- "A reasonable Kenyan reader" is a real judgement call, and one adjudicator
  cannot triangulate it. Two adjudicators would let us report human–human
  agreement, which is the true ceiling for the model number; with one, the
  reported figure is agreement with *this* reader.
- Sarcasm, and framing that works through omission rather than word choice, are
  the known weak spots. Both surface as low-confidence disagreements.
- The rules were written against national English-language political and
  business coverage. Vernacular-station reporting, county-level coverage, and
  heavily Sheng-inflected copy are less well covered.

---

## Appendix — labelling prompt

Model: `claude-opus-5`, adaptive thinking, structured outputs pinned to the §3
schema so the shape is guaranteed rather than parsed hopefully. Bulk runs go
through the Batch API at half cost. Ship `fallbacks` on the request: political
reporting is exactly the content a safety classifier may decline, and a refusal
arrives as HTTP 200 with `stop_reason: "refusal"`, so unhandled it looks like a
silently empty label rather than an error.

```
You are labelling Kenyan news articles for entity-scoped tone, following the
definition below exactly. The definition overrides any intuition you have about
sentiment.

<definition>
tone is the stance the article, as written, takes toward a named entity:
whether its framing, word choice, and selection of detail leave a reasonable
Kenyan reader with a worse, unchanged, or better impression of that entity's
conduct or standing.

You are NOT scoring: whether the events described are good or bad; whether the
article is pleasant to read; the sentiment of people quoted in it.

negative — the article's framing damages the entity: blame attributed, adverse
  finding reported as fact, critical characterisation in the article's own
  voice, unflattering detail foregrounded without counterweight.
positive — the article's framing credits the entity: achievement reported as
  fact, praise in the article's own voice, favourable framing adopted without
  attribution.
neutral  — the article reports events and attributes evaluative claims to their
  sources without adopting a posture. Straight reportage is neutral even when
  the events are catastrophic.
</definition>

<rules>
R1 A negative event is not a negative tone unless the article attributes blame.
R2 A quoted attack on X is neutral toward X unless the article amplifies it:
   repeats it in its own voice, headlines it unattributed, or omits an
   obviously available response.
R3 "charged with" / "under investigation" is neutral toward the accused.
   "convicted" / "found by the Auditor-General to have" is negative.
R4 The headline is part of the article and is the heaviest single piece of
   evidence for framing.
R5 If the article takes no posture toward an entity, omit it. Do not emit
   neutral rows for entities merely mentioned.
R6 Attributed official claims are neutral; the same claims adopted in the
   article's own voice are positive.
R7 Judge Swahili and Sheng on Kenyan meaning, not on English lexicon:
   maandamano (protests) is a neutral event descriptor; wash wash (fraud) is
   strongly negative; tanga tanga and kieleweke are neutral faction labels;
   hustler is in-group political self-identification, not an insult.
R8 In sport, a loss is negative toward the loser and a win positive toward the
   winner. Obituaries are positive toward the deceased.
R9 Label satire on its actual posture, not its literal surface; if the
   direction is ambiguous, confidence <= 0.5.
</rules>

Label every named entity that appears in the headline or first two paragraphs,
or is the subject or object of a main clause at least twice. At most five,
ranked by prominence. Canonicalise names ("President Ruto" and "William Ruto"
are one subject).

For each, return tone, subject, subject_type, confidence, and evidence — a
verbatim span of at most 200 characters from the article that supports the
tone. If no span supports it, the tone is neutral.

confidence is your probability that a second careful reader applying this
definition returns the same tone. Be calibrated: use the full range, and go
below 0.5 when the framing is genuinely mixed.

<article id="{id}">
{headline}

{body}
</article>
```
