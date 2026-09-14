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
head_table(
    doc,
    ["File", "Contents"],
    [
        (
            "docs\\SENTIMENT.md",
            "The label definition. Chosen definition, the schema, three class "
            "definitions, nine decision rules for the cases that actually decide the "
            "number, confidence bands, entity-selection test, annotation protocol, "
            "stated limits, and the labelling prompt derived from the rules.",
        ),
        (
            "docs\\README-sentiment-section.md",
            "Drop-in README section: the definition in brief, the agreement table ready "
            "for real numbers, and the argument against off-the-shelf models.",
        ),
        (
            "docs\\agreement.py",
            "Scorer. Raw agreement, Cohen's κ, 3×3 confusion matrix, per-class "
            "agreement, agreement by confidence band, prior re-weighting, and a "
            "disagreement listing with direction.",
        ),
        (
            "build_news.py",
            "Baseline copy of the deployed generator, committed unmodified.",
        ),
    ],
    widths=(2.1, 4.1),
)

# ---------------------------------------------------------------- outstanding
doc.add_heading("9. Outstanding", level=1)

p = doc.add_paragraph()
r = p.add_run("Blocked on you: ")
r.bold = True
p.add_run("gcloud authentication. Run in the Claude prompt:")
code_block(doc, "! /home/mnm/google-cloud-sdk/bin/gcloud auth login --no-launch-browser")
doc.add_paragraph(
    "Until this is done, files can only move between the VM and the working copy by "
    "copy-paste, and changes cannot be tested against the live box."
)

p = doc.add_paragraph()
r = p.add_run("Open decision: ")
r.bold = True
p.add_run(
    "whether to label on headline plus standfirst only (cheap, self-contained, but "
    "thinner evidence), or to fetch article bodies from the source links (faithful to the "
    "full rubric, but adds scraping, fragility, and a slower cron). Recommendation is the "
    "former, with the rubric explicitly scoped to the evidence actually available."
)

doc.add_paragraph("Remaining build:")
for t in [
    "store.py — SQLite article and label storage (must come first)",
    "label.py — Anthropic labelling against the frozen rubric, structured output",
    "handcheck.py — blind adjudication CLI for the 50-pair sample",
    "build_news.py — integrate fetch → store → label → render",
    "Display tone in the rendered cards",
    "Virtual environment, requirements.txt, API key placement, update_news.sh changes",
    "Deploy back to the VM once reviewed",
]:
    doc.add_paragraph(t, style="List Bullet")

# ---------------------------------------------------------------- footer
doc.add_paragraph()
foot = doc.add_paragraph()
fr = foot.add_run(
    "Nothing on the live VM has been modified. All work so far is local to "
    "D:\\kenya-daily-brief and under git."
)
fr.italic = True
fr.font.size = Pt(9)
fr.font.color.rgb = GREY

doc.save(OUT)
print(f"wrote {OUT}")
