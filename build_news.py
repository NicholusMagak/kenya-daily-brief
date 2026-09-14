#!/usr/bin/env python3

import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from html import escape
from datetime import datetime

import store

# Nairobi, not the VM's locale. The VM runs on Irish time, which stamped a
# Kenyan news site in IST.
try:
    from zoneinfo import ZoneInfo
    NAIROBI = ZoneInfo("Africa/Nairobi")
except Exception:
    NAIROBI = None

OUTPUT = os.environ.get(
    "KDB_OUTPUT",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"),
)

SUMMARY_CHARS = 220

TONE_LABEL = {
    "negative": "negative",
    "neutral": "neutral",
    "positive": "positive",
}

FEEDS = [
    {
        "category": "General Kenya News",
        "source": "Standard Kenya",
        "url": "https://www.standardmedia.co.ke/rss/kenya.php"
    },
    {
        "category": "Politics",
        "source": "Standard Politics",
        "url": "https://www.standardmedia.co.ke/rss/politics.php"
    },
    {
        "category": "Economy / Business",
        "source": "Standard Business",
        "url": "https://www.standardmedia.co.ke/rss/business.php"
    },
    {
        "category": "Sports",
        "source": "Standard Sports",
        "url": "https://www.standardmedia.co.ke/rss/sports.php"
    },
    {
        "category": "General Kenya News",
        "source": "Kenya News Agency",
        "url": "https://www.kenyanews.go.ke/feed/"
    },
    {
        "category": "Nation Africa",
        "source": "Nation Africa",
        "url": "https://nation.africa/kenya/rss.xml"
    }
]

def fetch_feed(url):
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"}
    )

    with urllib.request.urlopen(req, timeout=20) as response:
        return response.read()

def clean_text(value):
    if value is None:
        return ""
    return (
        value.replace("<![CDATA[", "")
        .replace("]]>", "")
        .replace("&nbsp;", " ")
        .strip()
    )

def get_child_text(item, name):
    child = item.find(name)
    if child is None or child.text is None:
        return ""
    return clean_text(child.text)

def collect_stories():
    stories = []

    for feed in FEEDS:
        try:
            data = fetch_feed(feed["url"])
            root = ET.fromstring(data)
            channel = root.find("channel")

            if channel is None:
                continue

            items = channel.findall("item")[:5]

            for item in items:
                stories.append({
                    "category": feed["category"],
                    "source": feed["source"],
                    "title": get_child_text(item, "title"),
                    "link": get_child_text(item, "link"),
                    "summary": get_child_text(item, "description"),
                    "date": get_child_text(item, "pubDate"),
                    "error": False
                })

        except Exception as error:
            # Kept on the page because a silently missing feed is worse than a
            # visible one, but flagged so it never reaches the corpus. Stored
            # and labelled, these become garbage rows that quietly inflate the
            # agreement rate.
            stories.append({
                "category": feed["category"],
                "source": feed["source"],
                "title": "Could not fetch feed",
                "link": feed["url"],
                "summary": str(error),
                "date": "",
                "error": True
            })

    return stories

def persist(stories):
    """Store real stories and attach their ids. Returns (conn, new_count)."""
    conn = store.connect()
    new = 0

    for story in stories:
        if story["error"] or not story["link"]:
            story["id"] = None
            continue

        aid, is_new = store.upsert_article(
            conn,
            link=story["link"],
            title=story["title"],
            standfirst=story["summary"],   # full text: truncation is display-only
            source=story["source"],
            category=story["category"],
            pub_date=story["date"],
        )
        story["id"] = aid
        new += 1 if is_new else 0

    conn.commit()
    return conn, new

def load_labels(conn):
    rows = conn.execute(
        "SELECT article_id, subject, tone, confidence FROM labels"
        " WHERE labeller = 'model' ORDER BY article_id, subject"
    ).fetchall()

    by_article = {}
    for row in rows:
        by_article.setdefault(row["article_id"], []).append(row)
    return by_article

def build_tone_html(labels):
    if not labels:
        return ""

    pills = ""
    for label in labels:
        pills += (
            f'<span class="tone tone-{escape(label["tone"])}">'
            f'{escape(label["subject"])}'
            f'<em>{escape(TONE_LABEL[label["tone"]])}</em>'
            f'</span>'
        )
    return f'<div class="tones">{pills}</div>'

def build_html(stories, labels_by_article):
    stamp = datetime.now(NAIROBI) if NAIROBI else datetime.now()
    now = stamp.strftime("%A %d %B %Y, %H:%M") + (" EAT" if NAIROBI else "")

    categories = []
    for story in stories:
        if story["category"] not in categories:
            categories.append(story["category"])

    sections = ""

    for category in categories:
        sections += f"""
        <section>
          <h2>{escape(category)}</h2>
        """

        for story in [s for s in stories if s["category"] == category]:
            tones = build_tone_html(labels_by_article.get(story.get("id"), []))
            sections += f"""
            <article class="card">
              <div class="source">{escape(story["source"])}</div>
              <h3><a href="{escape(story['link'])}" target="_blank" rel="noopener noreferrer">{escape(story['title'])}</a></h3>
              <p>{escape(story["summary"][:SUMMARY_CHARS])}</p>
              {tones}
              <small>{escape(story["date"])}</small>
            </article>
            """

        sections += """
        </section>
        """

    html = f"""
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Kenya Daily Brief</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>
    body {{
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f3f4f6;
      color: #111827;
    }}

    header {{
      background: #111827;
      color: white;
      padding: 20px;
      position: sticky;
      top: 0;
    }}

    header h1 {{
      margin: 0;
      font-size: 24px;
    }}

    header p {{
      margin: 6px 0 0;
      color: #d1d5db;
      font-size: 14px;
    }}

    main {{
      max-width: 850px;
      margin: auto;
      padding: 16px;
    }}

    h2 {{
      border-left: 5px solid #16a34a;
      padding-left: 10px;
      font-size: 20px;
      margin-top: 28px;
    }}

    .card {{
      background: white;
      border-radius: 14px;
      padding: 16px;
      margin-bottom: 12px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.06);
    }}

    .source {{
      color: #16a34a;
      font-weight: bold;
      font-size: 12px;
      margin-bottom: 6px;
    }}

    h3 {{
      font-size: 17px;
      margin: 0 0 8px;
      line-height: 1.35;
    }}

    a {{
      color: #111827;
      text-decoration: none;
    }}

    a:hover {{
      text-decoration: underline;
    }}

    p {{
      color: #374151;
      font-size: 14px;
      line-height: 1.5;
    }}

    small {{
      color: #6b7280;
      font-size: 12px;
    }}

    .tones {{
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      margin: 10px 0 8px;
    }}

    .tone {{
      display: inline-flex;
      align-items: baseline;
      gap: 6px;
      border-radius: 999px;
      padding: 3px 10px;
      font-size: 12px;
      border: 1px solid;
    }}

    .tone em {{
      font-style: normal;
      font-size: 11px;
      opacity: 0.75;
    }}

    .tone-negative {{
      background: #fef2f2;
      border-color: #fecaca;
      color: #991b1b;
    }}

    .tone-neutral {{
      background: #f3f4f6;
      border-color: #d1d5db;
      color: #374151;
    }}

    .tone-positive {{
      background: #f0fdf4;
      border-color: #bbf7d0;
      color: #166534;
    }}

    footer {{
      text-align: center;
      padding: 30px;
      color: #6b7280;
      font-size: 12px;
      line-height: 1.6;
    }}
  </style>
</head>
<body>
  <header>
    <h1>Kenya Daily Brief</h1>
    <p>Updated: {escape(now)}</p>
  </header>

  <main>
    {sections}
  </main>

  <footer>
    Tone labels are entity-scoped: they describe the stance each item takes
    toward a named person or body, not whether the news is good or bad.
    Labelled from headline and standfirst only, against a
    <a href="/sentiment.html" style="color:#16a34a">written definition</a>.<br>
    Built with Google Cloud Free Tier, RSS, Python and shell script.
  </footer>
</body>
</html>
"""
    return html

def main():
    stories = collect_stories()
    conn, new = persist(stories)
    labels_by_article = load_labels(conn)
    conn.close()

    html = build_html(stories, labels_by_article)

    with open(OUTPUT, "w", encoding="utf-8") as file:
        file.write(html)

    labelled = sum(1 for s in stories if labels_by_article.get(s.get("id")))
    print(f"{len(stories)} stories, {new} new, {labelled} with tone labels -> {OUTPUT}")

    # The definition the footer links to. Rendered from the same SENTIMENT.md
    # the labeller is prompted from, so the published page cannot drift from
    # the rubric actually in use.
    # Flat beside the script on the VM; under docs/ in the git working copy.
    here = os.path.dirname(os.path.abspath(__file__))
    rubric = next(
        (p for p in (os.path.join(here, "SENTIMENT.md"),
                     os.path.join(here, "docs", "SENTIMENT.md"))
         if os.path.exists(p)),
        os.path.join(here, "SENTIMENT.md"),
    )
    if os.path.exists(rubric):
        import render_doc

        html = render_doc.page(
            render_doc.render(re.sub(r"\A#\s+.*\n", "", open(rubric, encoding="utf-8").read())),
            "The sentiment label definition",
            "How tone is defined, and the rules used to decide it",
        )
        with open(os.path.join(os.path.dirname(OUTPUT), "sentiment.html"), "w",
                  encoding="utf-8") as file:
            file.write(html)
        print(f"rendered sentiment.html from {os.path.basename(rubric)}")
    else:
        print(f"note: {rubric} not found — sentiment.html not refreshed")

if __name__ == "__main__":
    main()
