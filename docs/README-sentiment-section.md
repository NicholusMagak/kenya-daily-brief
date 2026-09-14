<!-- Drop-in README section. Fill the bracketed numbers after running agreement.py. -->

## Sentiment

### What the label means

Sentiment here is **entity-scoped article tone**, not document sentiment and not
reader-facing positivity:

> the stance the article, as written, takes toward a named entity — whether its
> framing, word choice, and selection of detail leave a reasonable Kenyan reader
> with a worse, unchanged, or better impression of that entity's conduct or
> standing.

The unit is the `(article, entity)` pair. One article about a county audit
produces separate labels for the governor, the Auditor-General, and the assembly,
because a single document-level score would average a condemnation and a
vindication into a meaningless neutral.

```json
{ "tone": "negative|neutral|positive", "subject": "str", "confidence": 0.0 }
```

Two consequences worth stating plainly. A negative *event* is not a negative
*tone*: "Floods displace 400 in Tana River" is negative toward nobody unless the
article assigns blame. And a quoted attack is neutral: if the article reports
that A accused B, that is the article doing its job, and it only becomes negative
toward B if the article amplifies the charge in its own voice.

The full rubric — all nine decision rules, the entity-selection test, the
confidence bands, and the labelling prompt derived from them — is in
[`SENTIMENT.md`](./SENTIMENT.md). It was frozen before adjudication began.

### How well it works

Labels are produced by `claude-opus-5` prompted directly from the rubric above.
To find out whether that works, **50 `(article, entity)` pairs were hand-checked
against the same rubric**, sampled stratified by predicted tone and adjudicated
blind — the model's output was hidden until every human label was recorded.

| Metric | Value |
|---|---|
| Pairs adjudicated | 50 |
| Raw agreement | **[XX]%** |
| Cohen's κ | [0.XX] |
| Agreement, negative | [XX]% |
| Agreement, neutral | [XX]% |
| Agreement, positive | [XX]% |
| Agreement at confidence ≥ 0.9 | [XX]% |
| Agreement at confidence 0.5–0.7 | [XX]% |

Reproduce with `python agreement.py model_labels.csv human_labels.csv`.

Both numbers are reported because either alone misleads. On a three-class task
where most Kenyan reportage is genuinely neutral, a classifier that answered
"neutral" every time would score around 60% raw; κ corrects for that
agreement-by-chance. The sample is stratified, so the headline figure is
re-weighted by the corpus class prior — the raw sample rate would overstate
performance on the rare classes.

This is agreement with **one** adjudicator applying the rubric, which is the
honest framing: it is not a claim of correctness. Two adjudicators would give a
human–human ceiling to compare the model against, and that is the main thing
missing from this evaluation.

[Interpretation of the disagreements goes here once measured — the confusion
matrix is the useful part. Which direction does the model err, and does it
cluster in one rule?]

### Why not an off-the-shelf sentiment model

VADER, TextBlob, and the usual Hugging Face sentiment checkpoints were
considered and rejected. Four reasons, in rough order of how badly each one
bites:

**They cannot answer the question being asked.** They return one polarity score
for a whole document. This project needs a stance toward a *named entity*, and
there is no correct document-level answer for an article that condemns one actor
while vindicating another. This alone rules them out, independent of accuracy.

**Their training domain is wrong in a specific, predictable way.** VADER's
lexicon is built from social media and product-review text; the standard
transformer checkpoints are fine-tuned on SST-2, IMDB, or Yelp. Reviews encode
*the writer's feelings about a thing*, so those models learn to read event
valence as stance — exactly the conflation the rubric spends R1, R2, and R3
ruling out. News reports terrible events in neutral prose, and a review-trained
model scores a straight fatal-accident report as strongly negative when the
article takes no posture toward anyone at all.

**They do not read Kenyan English, Swahili, or Sheng.** Kenyan reporting
code-switches mid-sentence and mid-headline, and the relevant vocabulary is
absent from an English sentiment lexicon or gets scored on its English
appearance. `maandamano` is a neutral descriptor for protests. `wash wash` is
money-laundering fraud and strongly negative toward whoever it attaches to.
`tanga tanga` and `kieleweke` are faction names carrying no valence. `hustler`
is in-group political self-identification, not an insult. `mzee` is respectful.
None of these are in an English lexicon, and subword tokenizers trained on
English fragment them into pieces that carry meanings nobody intended.

**There is no benchmark to validate against.** No labelled Kenyan-news sentiment
set exists that would let us report an off-the-shelf model's accuracy on this
domain, so adopting one would mean shipping an unmeasured number. That absence
is precisely why the hand-check above is the evaluation — a stated agreement
rate against a written-down definition is worth more than an unmeasured
classifier with a citation.

The tradeoff being accepted: LLM labelling costs money per article and is slower
than a lexicon. The Batch API halves the cost, and for a summary app that labels
on ingest rather than per request, neither constraint binds.
