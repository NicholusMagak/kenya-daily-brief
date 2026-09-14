# Kenya Daily Brief

A daily digest of Kenyan news, aggregated from RSS feeds and labelled for
entity-scoped sentiment. Runs on a Google Compute Engine VM, rendered to static
HTML and served by nginx.

Live: http://8.231.166.151/

```
build_news.py    fetch feeds -> store articles -> render index.html
store.py         SQLite corpus: articles, labels, run audit
label.py         label stored articles with an LLM, per the rubric
handcheck.py     blind human adjudication of a stratified sample
docs/agreement.py  score model labels against human labels
docs/SENTIMENT.md  the label definition — read this first
```

---

## Sentiment

### What the label means

Sentiment here is **entity-scoped tone**, not document sentiment and not
reader-facing positivity:

> the stance the text, as written, takes toward a named entity — whether its
> framing, word choice, and selection of detail leave a reasonable Kenyan reader
> with a worse, unchanged, or better impression of that entity's conduct or
> standing.

The unit is the `(article, entity)` pair. One item about a county audit produces
separate labels for the governor, the auditor, and the assembly, because a single
document-level score would average a condemnation and a vindication into a
meaningless neutral.

```json
{ "tone": "negative|neutral|positive", "subject": "str", "confidence": 0.0 }
```

Two consequences worth stating plainly. A negative *event* is not a negative
*tone*: "16 injured as Golbo protests force suspension of land registration" is
negative toward nobody, because no blame is attributed. And a reported accusation
is neutral toward **both** parties: "Sifuna accuses Ruto of undermining
devolution" is neutral toward Ruto, because the verb `accuses` carries the
attribution — the publication is not asserting it.

**The labeller sees only the headline and the RSS standfirst — never the article
body.** This is an aggregator; it does not fetch source pages. Every rule in the
rubric is written to be decidable on one to three sentences, and the labels are
honestly described as standfirst-level tone rather than article-level tone.

The full rubric — nine decision rules, the entity-selection test, confidence
bands, the annotation protocol, and the stated limits — is in
[`docs/SENTIMENT.md`](docs/SENTIMENT.md). It is versioned
(`v1.0-headline-standfirst`), that version is stored on every label row, and
labels from different rubric versions are never compared.

### How well it works

Labels are produced by `claude-opus-5`, prompted directly from the rubric. To
find out whether that works, **50 `(article, entity)` pairs were hand-checked**
against the same rubric — sampled stratified by predicted tone, and adjudicated
blind: `handcheck.py` shows the headline, the standfirst, and the entity, and
hides the model's tone, confidence, and evidence until every human label is in.

| Metric | Value |
|---|---|
| Pairs adjudicated | _pending_ |
| Raw agreement | **_pending_** |
| Cohen's κ | _pending_ |
| Agreement, negative | _pending_ |
| Agreement, neutral | _pending_ |
| Agreement, positive | _pending_ |
| Agreement at confidence ≥ 0.9 | _pending_ |
| Agreement at confidence 0.5–0.7 | _pending_ |

> These fill in once the corpus has enough articles to draw 50 pairs. The
> pipeline that produces them is built and tested; the number is not invented in
> advance.

Reproduce:

```bash
python3 store.py export
python3 docs/agreement.py model_labels.csv human_labels.csv --corpus corpus_labels.csv
```

Both numbers are reported because either alone misleads. On a three-class task
where most Kenyan reportage is genuinely neutral, a labeller that answered
"neutral" every time would score around 60% raw; κ corrects for that
agreement-by-chance. The sample is stratified, so the headline figure is
re-weighted by the corpus class prior — the raw sample rate would overstate
performance on the rare classes.

This is agreement with **one** adjudicator applying the rubric, which is the
honest framing: it is not a claim of correctness. Two adjudicators would give a
human–human ceiling to compare the model against, and that is the main thing
missing from this evaluation.

### Why not an off-the-shelf sentiment model

VADER, TextBlob, and the usual Hugging Face sentiment checkpoints were
considered and rejected. Four reasons, in rough order of how badly each bites:

**They cannot answer the question being asked.** They return one polarity score
for a whole document. This project needs a stance toward a *named entity*, and
there is no correct document-level answer for an item that condemns one actor
while vindicating another. This alone rules them out, independent of accuracy.

**Their training domain is wrong in a specific, predictable way.** VADER's
lexicon is built from social media and product-review text; the standard
transformer checkpoints are fine-tuned on SST-2, IMDB, or Yelp. Reviews encode
*the writer's feelings about a thing*, so those models learn to read event
valence as stance — exactly the conflation rules R1, R2 and R3 exist to prevent.
News reports terrible events in neutral prose, and a review-trained model scores
a straight fatal-accident report as strongly negative when the text takes no
posture toward anyone at all.

**They do not read Kenyan English, Swahili, or Sheng.** Kenyan reporting
code-switches mid-sentence and mid-headline, and the relevant vocabulary is
absent from an English sentiment lexicon or scored on its English appearance.
`maandamano` is a neutral descriptor for protests. `wash wash` is
money-laundering fraud, strongly negative toward whoever it attaches to.
`tanga tanga` and `kieleweke` are faction names carrying no valence. `hustler` is
in-group political self-identification, not an insult. `mzee` is respectful. None
are in an English lexicon, and subword tokenizers trained on English fragment
them into pieces carrying meanings nobody intended.

**There is no benchmark to validate against.** No labelled Kenyan-news sentiment
set exists that would let us report an off-the-shelf model's accuracy on this
domain, so adopting one would mean shipping an unmeasured number. That absence is
precisely why the hand-check is the evaluation: a stated agreement rate against a
written-down definition is worth more than an unmeasured classifier with a
citation.

The tradeoff accepted: LLM labelling costs money per article and is slower than a
lexicon. At roughly 25–30 new articles a day, labelled once on ingest rather than
per request, neither constraint binds.

---

## Running it

### Local

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...

python3 build_news.py     # fetch + store + render
python3 label.py          # label anything new
python3 build_news.py     # re-render so new labels appear
python3 store.py          # corpus stats
```

`label.py --dry-run` prints the exact prompt for the next pending article and
makes no API call. Use it after any rubric edit.

### On the VM

```
/opt/kenya-news/
  build_news.py  store.py  label.py  handcheck.py
  .venv/                    # python3 -m venv /opt/kenya-news/.venv
  kenya_news.db             # the corpus
  update_news.sh            # cron: 30 6 * * *
/etc/kenya-news.env         # ANTHROPIC_API_KEY, chmod 600, root-owned
/var/www/html/index.html    # published output
```

Ubuntu 26.04 enforces PEP 668, so the Anthropic SDK cannot be installed into
system Python — hence the venv. `update_news.sh` treats labelling as non-fatal:
if it fails, the page still publishes with the labels it already had.

### Hand-checking

```bash
python3 handcheck.py            # 50 pairs, resumable, blind
python3 handcheck.py --status
```

The same `--seed` always draws the same sample, so an interrupted session
resumes rather than silently re-drawing.

---

## Design notes

**Storage came first.** The original version was stateless — fetch, render,
overwrite, forget. That makes the hand-check impossible: you cannot sample 50
articles from a corpus that does not exist, and you could never re-run the
measurement later. `store.py` (SQLite, stdlib) is the corpus.

**Standfirsts are stored untruncated.** The site displays 220 characters; the
labeller gets the full text. Truncating the evidence we label on would be a
self-inflicted wound.

**Failed feeds never reach the corpus.** When a feed times out, the generator
still renders a "Could not fetch feed" card — a silently missing section is worse
than a visible failure — but the entry is flagged and excluded from storage and
labelling. Stored and labelled, those become garbage rows that quietly inflate
the agreement rate.

**Refusals are recorded, not swallowed.** A safety classifier can decline a
request: HTTP 200, `stop_reason: "refusal"`, no usable content. Unhandled, that
looks identical to an article with no labelable entities. `label_runs` records
what happened for every attempt, so `refused`, `error`, and "genuinely no
entities" stay distinguishable.

**Timestamps are Africa/Nairobi.** The VM runs on Irish time, which was stamping
a Kenyan news site in IST.
