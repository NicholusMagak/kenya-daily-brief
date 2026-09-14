# Sentiment label definition

**Rubric version: `v1.0-headline-standfirst`**

This document defines the label. It is the specification the LLM labeller is
prompted from and the rubric the human adjudicator scores against. If the two
ever disagree about what a label *means*, this file wins and both get re-run.

The version string is stored on every label row. If this document changes, the
version changes, and model and human labels from different versions are never
compared — a rubric edited between labelling and adjudication measures nothing.

## 0. What the labeller actually sees

**Headline plus standfirst. Not the article body.**

Kenya Daily Brief is an RSS aggregator. It reads each feed's `<description>`
field and never fetches the article itself, so the complete evidence for a label
is a headline and one to three sentences. For example, the entire input for one
story is:

> **Sifuna accuses Ruto of undermining devolution**
> Nairobi Senator Edwin Sifuna has accused President William Ruto of undermining
> devolution through delays in the disbursement of funds to counties.

Every rule below is written to be decidable on that much text and no more. This
is a real limitation, stated here rather than quietly assumed away — see §9. It
is also why §7's entity test counts appearances rather than syntactic roles, and
why the cap is three entities rather than five.

Standfirsts are stored untruncated for labelling. The site's 220-character cut
is a display concern and must not reach the labeller.

## 1. The unit of analysis

**The unit is the `(article, entity)` pair, not the article.**

A Kenyan news item routinely credits one actor and damages another in a single
sentence — the Sifuna example above is negative toward Ruto and neutral toward
Sifuna, who is merely reported as speaking. A document-level score averages those
into a neutral that describes nothing. So we never label "the article". We label
its posture toward one named entity at a time, and an item with three salient
entities produces three rows.

## 2. The definition we chose

> **`tone` is the stance the text, as written, takes toward a named entity:
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
| **The sentiment of quoted speakers** | Reporting that A accused B is not the text being negative toward B. See R2. |
| **The item's overall mood** | Mood is a property of a text; we are labelling a directed relation. |

## 3. Schema

One record per `(article, entity)` pair:

```json
{
  "article_id":   "str      — sha256 of the article link",
  "subject":      "str      — the entity as canonically named",
  "subject_type": "person | organisation | government_body | party | place | company",
  "tone":         "negative | neutral | positive",
  "confidence":   "float    — 0.0–1.0, see §6",
  "evidence":     "str      — a verbatim span from headline or standfirst, ≤200 chars"
}
```

`evidence` is **required**, and it earns its place: it forces the labeller to
point at text rather than at a vibe, it makes a human check take seconds instead
of a re-read, and where the span doesn't support the tone you have found a bad
label without needing to re-adjudicate anything.

## 4. The three classes

**negative** — the framing damages the entity. Blame is attributed, an adverse
finding is reported as fact, the entity's conduct is characterised critically in
the text's own voice, or unflattering detail is selected and foregrounded.

**positive** — the framing credits the entity. Achievement is reported as fact,
praise appears in the text's own voice, or favourable framing is adopted without
attribution.

**neutral** — defined positively, not as a leftover bucket. The text reports what
happened and what people said, attributing evaluative claims to their sources,
without adopting a posture of its own. Straight reportage is neutral *even when
the events are catastrophic*. Most of the corpus should land here; a neutral rate
below ~50% is a signal the labeller has drifted into scoring event valence.

## 5. Decision rules

These exist because the edge cases are the whole difficulty, and an unwritten
rule is one the human adjudicator will apply differently on Tuesday than the
model applied on Monday.

**R1 — Event valence is not tone.** "16 injured, vehicles damaged as Golbo
protests force suspension of land registration" is negative toward nobody; it
reports an event. It would become negative toward an entity only if the text
attributed the injuries or the suspension to that entity's conduct.

**R2 — Quoted attacks are neutral by default.** If the text reports that A
accused B, tone toward B is **neutral** and tone toward A is **neutral** — clean
attribution is reporting. It flips to **negative** toward B only where the text
adopts the charge: states it as fact without attribution, or the headline asserts
it in the text's own voice. Note that a headline like "Sifuna accuses Ruto of
undermining devolution" *is* attributed — the verb "accuses" carries the
attribution — so it stays neutral.

**R3 — Accusation is not finding.** "Charged with", "under investigation",
"summoned by EACC", "accused of" → **neutral** toward the accused; a process is
being reported. "Convicted", "found by the Auditor-General to have", "ordered to
repay" → **negative**; an adverse fact is being reported.

**R4 — Headline and standfirst are weighted equally, and conflicts favour the
headline.** Both are the text. Where the headline frames harder than the
standfirst (common — headlines compress), label the pair as written and cite the
headline in `evidence`.

**R5 — Mere mention produces no row.** An entity named only as a location, a
dateline, an attribution tag ("police say"), or a bare passing reference is not
labelled at all. Do not emit `neutral` rows for entities the text has no posture
toward: it inflates the neutral class and flatters the agreement rate.

**R6 — Press-release framing.** Much Kenyan coverage reproduces official claims.
If the evaluative content is attributed ("Babu Owino vows to tackle garbage
menace", "police say") → **neutral**. If the text asserts it in its own voice
("the project will create 2,000 jobs") → **positive**; the text has taken on the
framing regardless of where it came from.

**R7 — Code-switching and Sheng are labelled on meaning, not on lexicon.** Judge
the Swahili or Sheng span for what it means in Kenyan usage. `maandamano`
(protests) is a neutral descriptor of an event, not a negative word. `wash wash`
(fraud) is strongly negative toward whoever it attaches to. Faction labels like
`tanga tanga` and `kieleweke` are neutral descriptors. `hustler` is in-group
political self-identification, not an insult. `mzee` is respectful. Where a term
is genuinely contested, lower `confidence` rather than guessing.

**R8 — Sport and obituary.** A defeat is negative toward the losing side and a
win positive toward the winner; this is the one place event valence and tone
legitimately coincide, because the text's subject *is* the entity's performance.
Obituaries and tributes are positive toward the deceased.

**R9 — Loaded characterisation in the text's own voice is tone.** "Ruto's Tata
Chemicals tantrum spooks investors" is **negative** toward Ruto: "tantrum" is the
publication's word, not a quoted source's. This is the main way a standfirst
carries tone, and it is the rule most likely to separate a careful labeller from
a careless one.

## 6. Confidence

The labeller's own probability that a second careful reader applying this
document would return the same `tone`.

| Band | Meaning |
|---|---|
| 0.9–1.0 | Explicit and unambiguous; the evidence span settles it alone. |
| 0.7–0.9 | Clear on a careful read; a hurried reader might differ. |
| 0.5–0.7 | Genuinely mixed framing, or the call turns on one contested rule. |
| < 0.5 | Coin-flip, or the standfirst is too thin to support a call. |

Confidence is only worth having if it is calibrated, so the hand-check reports
agreement **split by confidence band**. If agreement in the 0.9+ band is not
clearly higher than in the 0.5–0.7 band, the field is decoration and should
either be fixed or dropped from the schema.

## 7. Entity selection

An entity is labelled if **both** hold:

1. It is a **named** entity — a proper noun. Not "the government", not
   "residents", not "police" unqualified.
2. The headline or standfirst makes an **agentive or evaluative** claim about it:
   it acts, is acted upon, or is characterised. Appearing only as a location, a
   dateline, or an attribution tag does not qualify (R5).

Cap at **three** per article, ranked headline-first. Canonicalise before storing
— `William Ruto`, `President Ruto`, and `President William Ruto` collapse to one
subject string — because entity-scoped labels are worthless if the same person
appears under three keys.

## 8. Annotation and agreement protocol

The agreement number is the deliverable. It only means anything if the procedure
protects it:

1. **Sample 50 `(article, entity)` pairs**, stratified by *model-predicted* tone
   so the rare classes are actually represented. A random sample of a corpus this
   neutral-heavy would return ~40 neutrals and measure nothing.
2. **Adjudicate blind.** `handcheck.py` shows the headline, the standfirst, and
   the entity — and hides the model's tone, confidence, and evidence until every
   human label is recorded. Reading the prediction first turns the exercise into
   agreeing with it, which is the difference between a real number and a
   flattering one.
3. **The entity is given; the tone is judged.** The adjudicator is not asked to
   re-select entities, because the measured quantity is tone agreement.
   Entity-selection disagreement is reported separately by `agreement.py`.
4. **Freeze this document before adjudicating.** If a rule has to be added
   mid-check, note it, finish, bump the version, then re-run both sides.
5. **Report** raw agreement, Cohen's κ, the 3×3 confusion matrix, per-class
   agreement, and agreement by confidence band.

**Report κ alongside raw agreement, not instead of it.** On a three-class task
with a dominant neutral, a labeller that answered "neutral" every time would
score somewhere near 60% raw. κ corrects for that agreement-by-chance, so the
pair of numbers is honest where either alone is not. And because the sample is
stratified, sample-level agreement is not corpus-level agreement — re-weight by
the corpus class prior for the headline figure (`agreement.py --corpus` does
this).

## 9. Known limits of this definition

- **The evidence is thin.** One to three sentences cannot show what a full
  article shows: sourcing balance, what was omitted, whether a response was
  sought. R2 and R6 are therefore decided on the presence of attribution markers
  alone, which is a weaker test than reading the piece. Labels here are
  *standfirst-level* tone and should be described that way, never as
  article-level tone.
- **One adjudicator.** "A reasonable Kenyan reader" is a judgement call, and one
  person cannot triangulate it. Two adjudicators would let us report human–human
  agreement, which is the true ceiling for the model's number. With one, the
  reported figure is agreement with *this* reader — which is the honest framing,
  and is not a claim of correctness.
- **Sarcasm and framing-by-omission** are the known weak spots, and omission is
  largely invisible at this length. Both surface as low-confidence disagreements.
- **Source monoculture.** The corpus is dominated by Standard Media, whose
  house style is one publication's, not Kenyan journalism's. Nation Africa and
  KNA are configured but KNA has been timing out.
- **Sheng is rare in these feeds.** R7 is written for it, but national
  English-language wire copy carries relatively little, so R7 will be
  under-exercised — and correspondingly under-tested by the hand-check.
