# Kenya Daily Brief

**Live site:** http://8.231.166.151/

I'm a Kenyan studying in Dublin, and I wanted one simple thing: a single place to
catch up on news from home every morning, without jumping between half a dozen
news sites. Once that was working, a second question followed naturally. How are
people and institutions actually being *portrayed* in Kenyan news? That became
the sentiment side of this project.

---

## Project status

| Phase | What it does | Status |
|---|---|---|
| **1. Aggregation** | Pulls Kenyan news from RSS feeds every morning, stores it, and publishes a daily digest page | ✅ Live |
| **2. Sentiment** | Labels the tone each article takes toward the people and organisations it names | 🔨 Labelling built, evaluation in progress |
| **3. Next** | Publish evaluation results, then explore tone trends over time | 📋 Planned |

---

## How it works

At its core this is a small, scheduled data pipeline:

```
RSS feeds ──► build_news.py ──► store.py (SQLite) ──► label.py (LLM) ──► index.html ──► nginx
 Extract        fetch + clean      Load: corpus           Transform:          Render         Serve
                                   + run audit            sentiment labels
```

- **Extract:** `build_news.py` fetches articles from Kenyan news RSS feeds.
- **Load:** `store.py` saves every article into a SQLite corpus, along with an
  audit log of each run.
- **Transform:** `label.py` labels stored articles for sentiment using an LLM.
- **Publish:** the digest is rendered to static HTML and served by nginx on a
  Google Compute Engine VM.
- **Schedule:** a cron job runs `update_news.sh` every morning at 06:30.

**Tech:** Python, SQLite, Anthropic API, Google Cloud (Compute Engine), nginx, cron, Bash

---

## Phase 2: Sentiment, done properly

### The idea

Most sentiment tools give a whole article one score: positive, negative or
neutral. That doesn't work for news. A story about a county audit might condemn
the governor and vindicate the auditor in the same paragraph. Averaging that
gives you "neutral", which tells you nothing.

So this project measures **entity-scoped tone**: the stance an article takes
toward each named person or organisation separately. One article can produce
several labels.

```json
{ "tone": "negative|neutral|positive", "subject": "str", "confidence": 0.0 }
```

Two rules show why this matters:

- **A bad event is not a negative tone.** "16 injured as protests force
  suspension of land registration" blames nobody, so it's negative toward
  nobody.
- **A reported accusation is neutral.** In "Sifuna accuses Ruto of undermining
  devolution", the publication is reporting a claim, not making one, so the tone
  toward Ruto is neutral.

The full rubric (nine decision rules, confidence bands and stated limits) is in
[`docs/SENTIMENT.md`](docs/SENTIMENT.md). It's versioned, and the version is
stored on every label so results from different rubric versions are never mixed.

### Why not an off-the-shelf sentiment model?

I looked at VADER, TextBlob and standard Hugging Face sentiment models, and
ruled them out:

1. **They answer a different question.** They score whole documents, not stance
   toward a specific entity.
2. **They're trained on reviews and social media**, where negative events and
   negative opinions go together. News describes terrible events in neutral
   language.
3. **They don't understand Kenyan English, Swahili or Sheng.** `maandamano`
   (protests) is neutral. `wash wash` (money-laundering fraud) is strongly
   negative. `tanga tanga` and `kieleweke` are political faction names with no
   built-in tone. An English lexicon gets these wrong or ignores them.
4. **There's no Kenyan news sentiment benchmark** to validate them against.

The trade-off is that LLM labelling costs money per article. At around 25 to 30
new articles a day, labelled once when they arrive, that cost stays small.

### How I'm checking it (in progress)

An LLM label is only worth something if you measure it. The plan:

- Draw a **stratified sample of 50 article-entity pairs** from the corpus.
- Label them by hand with `handcheck.py`, **blind**: I see the headline and the
  entity, but not the model's answer until all my labels are in.
- Score agreement with `docs/agreement.py`, reporting both **raw agreement** and
  **Cohen's kappa** (kappa matters because most Kenyan reporting is neutral, so a
  model that always said "neutral" would still look decent on raw agreement).

The pipeline for this is built and tested. Results will be published here once
the corpus is large enough to draw the full sample. I'm not putting a number
up before it exists.

**Honest limits:** the labeller only sees the headline and RSS summary, not the
full article, so these are headline-level tone labels. And agreement with one
human checker is not proof of correctness; a second checker would give a
proper human-to-human baseline.

---

## Engineering decisions worth noting

- **Storage came first.** The first version just fetched and rendered, then
  forgot everything. You can't evaluate a model on data you didn't keep, so I
  added the SQLite corpus.
- **Failed feeds stay out of the data.** If a feed times out, the page shows a
  visible "could not fetch" card, but that entry never gets stored or labelled.
  Junk rows would quietly distort the evaluation.
- **Refusals are logged, not hidden.** If the API declines to label something,
  `label_runs` records it, so "refused", "error" and "nothing to label" stay
  distinguishable.
- **Labelling failures don't break the site.** If labelling fails, the page
  still publishes with the labels it already has.
- **Secrets stay out of the code.** The API key is read from the environment and
  lives in a locked-down env file on the server (`chmod 600`), never in the repo.
- **Timestamps use Nairobi time.** The VM runs on Irish time, which was stamping
  Kenyan news in the wrong time zone.

---

## Run it yourself

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=your-key-here

python3 build_news.py     # fetch, store and render
python3 label.py          # label new articles
python3 build_news.py     # re-render with the new labels
python3 store.py          # corpus stats
```

`python3 label.py --dry-run` prints the exact prompt for the next article
without calling the API.

Hand-checking:

```bash
python3 handcheck.py            # 50 pairs, blind, resumable
python3 handcheck.py --status
```

---

## Project files

| File | Purpose |
|---|---|
| `build_news.py` | Fetch feeds, store articles, render the page |
| `store.py` | SQLite corpus: articles, labels, run audit |
| `label.py` | Label stored articles with an LLM using the rubric |
| `handcheck.py` | Blind human labelling of a stratified sample |
| `update_news.sh` | Daily cron job on the VM |
| `docs/SENTIMENT.md` | The full sentiment rubric (start here for Phase 2) |
| `docs/agreement.py` | Scores model labels against human labels |
