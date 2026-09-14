#!/usr/bin/env python3
"""Generate PROJECT_LOG.docx — the running record of work on Kenya Daily Brief.

Re-run after each work session to refresh the document:
    python3 docs/make_project_log.py
"""

from docx import Document
from docx.shared import Pt, RGBColor, Inches
from docx.enum.text import WD_ALIGN_PARAGRAPH
from datetime import date
import os

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "PROJECT_LOG.docx")

MONO = "Consolas"
GREEN = RGBColor(0x16, 0xA3, 0x4A)
GREY = RGBColor(0x6B, 0x72, 0x80)


def mono(par, text):
    run = par.add_run(text)
    run.font.name = MONO
    run.font.size = Pt(9)
    return run


def code_block(doc, text):
    par = doc.add_paragraph()
    par.paragraph_format.left_indent = Inches(0.3)
    par.paragraph_format.space_after = Pt(6)
    mono(par, text)
    return par


def kv_table(doc, rows, widths=(2.2, 4.0)):
    table = doc.add_table(rows=0, cols=2)
    table.style = "Table Grid"
    for k, v in rows:
        cells = table.add_row().cells
        kp = cells[0].paragraphs[0]
        kr = kp.add_run(k)
        kr.bold = True
        kr.font.size = Pt(9)
        vp = cells[1].paragraphs[0]
        vr = vp.add_run(v)
        vr.font.size = Pt(9)
    for row in table.rows:
        row.cells[0].width = Inches(widths[0])
        row.cells[1].width = Inches(widths[1])
    doc.add_paragraph()
    return table


def head_table(doc, headers, rows, widths=None):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    for i, h in enumerate(headers):
        p = table.rows[0].cells[i].paragraphs[0]
        r = p.add_run(h)
        r.bold = True
        r.font.size = Pt(9)
    for row in rows:
        cells = table.add_row().cells
        for i, val in enumerate(row):
            p = cells[i].paragraphs[0]
            r = p.add_run(val)
            r.font.size = Pt(9)
    if widths:
        for row in table.rows:
            for i, w in enumerate(widths):
                row.cells[i].width = Inches(w)
    doc.add_paragraph()
    return table


doc = Document()

style = doc.styles["Normal"]
style.font.name = "Calibri"
style.font.size = Pt(10.5)

# ---------------------------------------------------------------- title
title = doc.add_heading("Kenya Daily Brief — Project Log", level=0)
sub = doc.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.LEFT
r = sub.add_run(
    "Adding entity-scoped sentiment analysis to the Kenya Daily Brief news aggregator\n"
    f"Working copy: D:\\kenya-daily-brief    ·    Log generated: {date.today():%d %B %Y}"
)
r.font.size = Pt(9.5)
r.font.color.rgb = GREY

# ---------------------------------------------------------------- brief
doc.add_heading("1. What was asked", level=1)
doc.add_paragraph(
    "Three changes to the existing Kenya Daily Brief webapp running on Google Cloud:"
)
for t in [
    "Define what “sentiment” means for this application and write the definition down, "
    "rather than adopting an off-the-shelf classifier and calling its output the label.",
    "Label articles with an LLM, hand-check 50 of them personally, and report the "
    "agreement rate between the two in the README.",
    "State plainly in the README why off-the-shelf sentiment models are a poor fit for "
    "Kenyan political reporting, code-switching, and Sheng.",
]:
    doc.add_paragraph(t, style="List Number")

doc.add_paragraph(
    "A complication at the outset: no record of the original build existed. The previous "
    "WSL installation had been deleted, so there was no conversation history, no memory "
    "entry, and no local source. The application had to be located from scratch."
)

# ---------------------------------------------------------------- step 1
doc.add_heading("2. Locating the application", level=1)
doc.add_paragraph(
    "Rather than reconstruct the project from description, the machine was searched for "
    "hard evidence. Every check came back negative, which is what established that the "
    "app had never been built on this installation:"
)
head_table(
    doc,
    ["Check", "Result"],
    [
        ("Memory directory and MEMORY.md index", "4 entries, none related"),
        ("All 7 Claude Code transcripts, grep “kenya”", "Only hit: a Windows folder listing"),
        ("gcloud / gsutil / firebase binaries", "Not installed"),
        ("~/.config/gcloud", "Does not exist"),
        ("Shell history, grep deploy commands", "No matches"),
        ("package.json / app.yaml / requirements.txt / Dockerfile", "None anywhere under /home/mnm"),
    ],
    widths=(3.4, 2.8),
)
doc.add_paragraph(
    "Once the URL was supplied, the live site identified itself directly. Reverse DNS "
    "resolved the host to a Google Compute Engine address, confirming the platform:"
)
code_block(
    doc,
    "http://8.231.166.151/\n"
    "  HTTP/1.1 200 OK\n"
    "  Server: nginx/1.28.3 (Ubuntu)\n"
    "  Content-Length: 18103\n"
    "  Last-Modified: Mon, 14 Sep 2026 05:30:23 GMT\n"
    "  <title>Kenya Daily Brief</title>\n\n"
    "reverse DNS → 151.166.231.8.bc.googleusercontent.com   (Compute Engine)",
)
doc.add_paragraph(
    "The page structure — sectioned RSS cards, a caught “Could not fetch feed / urlopen "
    "error timed out” message rendered as a card — indicated a Python generator writing "
    "static HTML, served by nginx. That inference proved correct."
)

# ---------------------------------------------------------------- step 2
doc.add_heading("3. Environment setup", level=1)
doc.add_paragraph(
    "The Google Cloud CLI was installed into the user's home directory using the archive "
    "method, deliberately avoiding sudo so that no password prompt could stall the install:"
)
code_block(
    doc,
    "curl -sSL -o gcloud-cli.tar.gz \\\n"
    "  https://dl.google.com/dl/cloudsdk/channels/rapid/downloads/"
    "google-cloud-cli-linux-x86_64.tar.gz\n"
    "tar -xzf gcloud-cli.tar.gz\n"
    "./google-cloud-sdk/install.sh --quiet --usage-reporting=false",
)
kv_table(
    doc,
    [
        ("Installed version", "Google Cloud SDK 584.0.0"),
        ("Location", "/home/mnm/google-cloud-sdk"),
        ("PATH", "Added to ~/.bashrc (backup written to ~/.bashrc.backup)"),
        ("Authentication", "NOT YET COMPLETED — see section 8"),
    ],
)

# ---------------------------------------------------------------- step 3
doc.add_heading("4. Discovery on the VM", level=1)
doc.add_paragraph(
    "The VM was inspected over the Google Cloud console SSH session. The application is "
    "small and entirely self-contained:"
)
kv_table(
    doc,
    [
        ("Instance", "kenya-news-vm"),
        ("OS", "Ubuntu 26.04 LTS, kernel 7.0.0-1003-gcp"),
        ("Application directory", "/opt/kenya-news/"),
        ("Generator", "build_news.py — 255 lines, Python 3"),
        ("Wrapper", "update_news.sh (runs the generator, sudo cp to docroot)"),
        ("Schedule", "cron: 30 6 * * * — daily at 06:30"),
        ("Web root", "/var/www/html/index.html, served by nginx"),
        ("Version control", "None — no .git on the VM"),
        ("Virtual environment", "None — system Python, zero dependencies"),
    ],
)

# ---------------------------------------------------------------- step 4
doc.add_heading("5. Source retrieved and placed under version control", level=1)
doc.add_paragraph(
    "The source was copied to the working folder on the D: drive and committed unmodified, "
    "so that every subsequent change is a reviewable diff against a known-good baseline "
    "and can be reverted:"
)
code_block(
    doc,
    "D:\\kenya-daily-brief\\\n"
    "  build_news.py            (baseline, exactly as deployed)\n"
    "  docs\\\n"
    "    SENTIMENT.md\n"
    "    README-sentiment-section.md\n"
    "    agreement.py\n"
    "    kdb-index.html         (captured live output, for reference)\n"
    "    make_project_log.py    (generates this document)\n\n"
    "git commit 30be3f3 — “Baseline: build_news.py as deployed on kenya-news-vm”",
)

# ---------------------------------------------------------------- findings
doc.add_heading("6. Findings that shape the work", level=1)
doc.add_paragraph(
    "Reading the source turned up several constraints. The first is the significant one — "
    "it changes the order of the work:"
)

p = doc.add_paragraph()
r = p.add_run("6.1  There is no persistence. ")
r.bold = True
p.add_run(
    "The directory contains only the script, its rendered output, a log, and the wrapper. "
    "Each 06:30 run fetches the feeds, builds HTML, and overwrites index.html. Yesterday's "
    "articles are gone. This blocks the hand-check directly: 50 articles cannot be sampled "
    "from a corpus that does not exist, and the agreement measurement could never be "
    "repeated. Article storage must therefore be built first, before any labelling. SQLite "
    "covers it and adds no dependency."
)

p = doc.add_paragraph()
r = p.add_run("6.2  Only headline and a 220-character standfirst are available. ")
r.bold = True
p.add_run(
    "The generator reads the RSS <description> field and truncates it: summary[:220]. "
    "Article bodies are never fetched. Any labelling therefore reads a headline plus a "
    "short standfirst, not a full article — a real constraint on the label definition, "
    "and one the rubric has to state rather than quietly assume away."
)

p = doc.add_paragraph()
r = p.add_run("6.3  Failed feeds are injected as fake articles. ")
r.bold = True
p.add_run(
    "The exception handler appends a pseudo-story titled “Could not fetch feed” with the "
    "error text as its summary. One is on the live site now (Kenya News Agency, timed out). "
    "These must be excluded from storage and labelling, or they become garbage rows that "
    "quietly inflate the agreement rate."
)

p = doc.add_paragraph()
r = p.add_run("6.4  Timestamps use VM local time. ")
r.bold = True
p.add_run(
    "datetime.now() returns the server's time, and the VM is on Irish time — so a Kenyan "
    "news site is stamped in IST rather than EAT. Minor for display, but article dating "
    "matters once a stored corpus exists."
)

p = doc.add_paragraph()
r = p.add_run("6.5  Adding an LLM introduces the first dependency. ")
r.bold = True
p.add_run(
    "The project currently imports only urllib, ElementTree, html.escape and datetime. "
    "The Anthropic SDK will be the first external package, and Ubuntu 26.04 enforces "
    "PEP 668 — so a virtual environment is required, and update_news.sh must be updated "
    "to use it. The API key needs a home outside the source and outside git."
)

# ---------------------------------------------------------------- decisions
doc.add_heading("7. Decisions taken", level=1)
head_table(
    doc,
    ["Decision", "Rationale"],
    [
        (
            "Sentiment = entity-scoped article tone",
            "The stance the article takes toward one named entity. A Kenyan article "
            "routinely praises one actor and condemns another in the same paragraph; a "
            "document-level score averages those into a meaningless neutral.",
        ),
        (
            "Unit is the (article, entity) pair",
            "Not the article. One article yields one row per salient entity.",
        ),
        (
            "Evidence span is a required field",
            "Forces the labeller to point at text rather than at a vibe, and makes each "
            "human check take seconds instead of a full re-read.",
        ),
        (
            "Report Cohen's κ alongside raw agreement",
            "Most Kenyan reportage is genuinely neutral, so a labeller answering "
            "“neutral” every time would score roughly 60% raw. κ corrects for "
            "agreement by chance; the pair is honest where either alone is not.",
        ),
        (
            "Adjudicate blind",
            "The model's label stays hidden until all 50 human labels are recorded. "
            "Reading the prediction first measures self-agreement, not accuracy.",
        ),
        (
            "Sample stratified, then re-weight",
            "A random 50 from this corpus would return mostly neutrals and measure "
            "nothing about the rare classes. The headline figure is re-weighted by the "
            "corpus class prior.",
        ),
        (
            "Storage before labelling",
            "Per finding 6.1 — the hand-check is impossible without a stable corpus.",
        ),
    ],
    widths=(2.1, 4.1),
)

# ---------------------------------------------------------------- deliverables
doc.add_heading("8. Produced so far", level=1)
doc.add_paragraph(
    "The scope decision was taken: label on headline plus standfirst, and narrow the "
    "rubric to say so explicitly, rather than applying a full-article rubric to 220 "
    "characters and hoping nobody checks."
)
head_table(
    doc,
    ["File", "Contents"],
    [
        (
            "docs\\SENTIMENT.md",
            "The label definition, version v1.0-headline-standfirst. Chosen definition, "
            "schema, three class definitions, nine decision rules, confidence bands, "
            "entity-selection test, annotation protocol and stated limits. Opens by "
            "stating exactly what the labeller sees.",
        ),
        (
            "store.py",
            "SQLite corpus — articles, labels, and a run audit table. Model and human "
            "labels coexist per (article, entity) because labeller is part of the "
            "primary key, which is what the agreement measurement needs. Also exports "
            "the three scoring CSVs.",
        ),
        (
            "label.py",
            "LLM labeller. claude-opus-5, adaptive thinking, structured output pinned "
            "to the schema. Handles refusals explicitly and records every attempt.",
        ),
        (
            "handcheck.py",
            "Blind adjudication CLI. Shows headline, standfirst and entity; hides the "
            "model's tone, confidence and evidence. Resumable on a fixed seed.",
        ),
        (
            "docs\\agreement.py",
            "Scorer. Raw agreement, Cohen's κ, 3×3 confusion matrix, per-class "
            "agreement, agreement by confidence band, corpus-prior re-weighting, and a "
            "disagreement listing with direction.",
        ),
        (
            "build_news.py",
            "Rewired: fetch → store → render, with tone badges on each card.",
        ),
        (
            "README.md",
            "Includes the definition, the agreement table, and the case against "
            "off-the-shelf sentiment models.",
        ),
        (
            "update_news.sh",
            "Adds venv activation, the API key env file, and a labelling pass that is "
            "non-fatal — a labelling failure must not take the site down.",
        ),
    ],
    widths=(1.7, 4.5),
)

doc.add_heading("8.1  Testing", level=2)
doc.add_paragraph(
    "The pipeline was run end to end locally against a copy of the corpus with "
    "synthetic labels, so the whole chain was exercised before any API key was "
    "involved: 26 stories fetched, 25 stored (the failed-feed card correctly excluded), "
    "51 labels injected, adjudication driven with scripted input, CSVs exported, and the "
    "scorer run. Tone badges were confirmed to render."
)
doc.add_paragraph(
    "That test found a real bug. save_labels() deletes an article's existing labels for "
    "a labeller before inserting — correct for the model, which emits every entity in "
    "one response, but wrong for the human, who adjudicates one entity at a time. Where "
    "the sample contained two entities from the same article, recording the second "
    "silently erased the first: ten adjudications, eight rows stored. Fixed by adding "
    "upsert_label() for single-pair writes. This is exactly the class of bug that would "
    "have quietly corrupted the agreement number rather than announcing itself."
)

# ---------------------------------------------------------------- outstanding
doc.add_heading("9. Outstanding", level=1)

doc.add_paragraph(
    "Both prerequisites are now complete: gcloud is authenticated against project "
    "kenyan-ai-news-summary, and the API key is in /etc/kenya-news.env on the VM. The "
    "system is deployed and live — see section 10."
)

doc.add_heading("9.1  Where the data lives", level=2)
doc.add_paragraph(
    "Three places, and it is worth being precise about which is authoritative:"
)
head_table(
    doc,
    ["Location", "What, and whose"],
    [
        (
            "VM persistent disk\n/opt/kenya-news/kenya_news.db",
            "The master corpus, once deployed. Your GCP project, Google's "
            "infrastructure, in the VM's region. Cron appends to it daily, so it is the "
            "only copy that stays current.",
        ),
        (
            "D:\\kenya-daily-brief\\",
            "The code, under git — authoritative for source. Also currently holds a "
            "25-article database from local testing, which will diverge from the VM "
            "once deployed and should be treated as scratch.",
        ),
        (
            "Anthropic API",
            "Headline and standfirst are sent for labelling. Public news text, but it "
            "does leave your infrastructure. Nothing else is transmitted.",
        ),
    ],
    widths=(2.1, 4.1),
)
doc.add_paragraph(
    "Recommended split, so no file is authoritative in two places: code flows from D: to "
    "the VM, data flows from the VM to D:. Run the hand-check over SSH against the VM's "
    "database rather than pulling it down, adjudicating locally, and pushing it back — "
    "cron writes to that file every morning, and a push-back would clobber whatever it "
    "added. Pull copies down for backup and analysis freely; just do not write to them "
    "and send them back."
)
doc.add_paragraph(
    "Volume is negligible: roughly 25–30 articles a day, a few megabytes a year."
)

doc.add_heading("9.2  Remaining", level=2)
for t in [
    "Accumulate enough articles to draw 50 (article, entity) pairs — 30 exist, so one "
    "more 06:30 cron run should clear it",
    "Run the blind hand-check (handcheck.py, over an interactive SSH session)",
    "Fill the agreement table in README.md with the measured figures",
    "Consider a second adjudicator, which would give a human–human ceiling",
]:
    doc.add_paragraph(t, style="List Bullet")

# ---------------------------------------------------------------- deployment
doc.add_heading("10. Deployment and first labelling run", level=1)
doc.add_paragraph(
    "Deployed to kenya-news-vm (us-west1-a, e2-micro, free tier). The live files were "
    "backed up first as *.bak-20260914-1244, so the previous version can be restored "
    "with three cp commands. Two environment problems surfaced and were fixed: the "
    "Ubuntu image was minimized and had no ensurepip, so python3.14-venv had to be "
    "installed before a virtual environment could be created; and the API key file had "
    "been placed root-owned at chmod 600, which the cron job — running under the user "
    "crontab, not root's — could not read, so labelling would have silently skipped "
    "every morning. Ownership was moved to the cron user."
)
doc.add_paragraph(
    "Two code bugs were found by running against the real API, both of which would have "
    "failed quietly rather than loudly:"
)
for t in [
    "An errored labelling attempt permanently retired an article from the queue, because "
    "the pending query excluded any article with any prior run record. All 20 articles "
    "that failed on a billing error would never have been retried. Only 'ok' and "
    "'refused' are final now.",
    "The output schema used maxItems on an array, which structured outputs rejects. The "
    "three-entity cap moved to the prompt and a client-side trim.",
]:
    doc.add_paragraph(t, style="List Bullet")

doc.add_heading("10.1  First results", level=2)
kv_table(
    doc,
    [
        ("Articles labelled", "20, producing 30 (article, entity) pairs, in 84 seconds"),
        ("Tone distribution", "20.0% negative · 56.7% neutral · 23.3% positive"),
        ("Articles given zero labels", "3"),
        ("Live", "Published to /var/www/html/index.html, 17 badged cards"),
    ],
)
doc.add_paragraph(
    "The neutral share sitting above 50% is the first indication that the labeller is "
    "scoring stance rather than event valence, which is what the rubric spends R1, R2 "
    "and R3 trying to enforce."
)
doc.add_paragraph(
    "Three cases chosen in advance as tests of the rules all came back correct: "
    "\u201cSifuna accuses Ruto of undermining devolution\u201d returned neutral toward "
    "both parties (R2 — the verb carries the attribution); \u201cRuto's Tata Chemicals "
    "tantrum spooks investors\u201d returned negative toward Ruto at 0.95, citing the "
    "headline (R9 — \u201ctantrum\u201d is the publication's word); and \u201cBabu Owino "
    "pledges good service\u201d returned neutral (R6 — an attributed promise, not one "
    "the text adopts)."
)
doc.add_paragraph(
    "More telling, three articles were correctly given no labels at all, including "
    "\u201cWoman killed in hit and run at Jacaranda rally\u201d and \u201c16 injured, "
    "vehicles damaged as Golbo protests force suspension of land registration\u201d. "
    "Both are violent events with no blame attributed and no named entity to attach it "
    "to (R1, R5). An off-the-shelf review-trained classifier would score both strongly "
    "negative. That is the argument of the README's final section, now demonstrated "
    "rather than asserted."
)

p = doc.add_paragraph()
r = p.add_run("These three canaries are not a measurement. ")
r.bold = True
p.add_run(
    "They were hand-picked in advance, and three cases chosen by the person who wrote "
    "the rules prove only that the rules are implementable. The agreement table in "
    "README.md stays marked pending until 50 pairs have been adjudicated blind."
)

# ---------------------------------------------------------------- footer
doc.add_paragraph()
foot = doc.add_paragraph()
fr = foot.add_run(
    "Live at http://8.231.166.151/ · working copy D:\\kenya-daily-brief under git · "
    "previous version recoverable from *.bak-20260914-1244 on the VM."
)
fr.italic = True
fr.font.size = Pt(9)
fr.font.color.rgb = GREY

doc.save(OUT)
print(f"wrote {OUT}")
