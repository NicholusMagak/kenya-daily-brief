#!/usr/bin/env python3

import urllib.request
import xml.etree.ElementTree as ET
from html import escape
from datetime import datetime

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

def build_html(stories):
    now = datetime.now().strftime("%A %d %B %Y, %H:%M")

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
            sections += f"""
            <article class="card">
              <div class="source">{escape(story["source"])}</div>
              <h3><a href="{escape(story['link'])}" target="_blank" rel="noopener noreferrer">{escape(story['title'])}</a></h3>
              <p>{escape(story["summary"])}</p>
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

    footer {{
      text-align: center;
      padding: 30px;
      color: #6b7280;
      font-size: 12px;
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
    Built with Google Cloud Free Tier, RSS, Python and shell script.
  </footer>
</body>
</html>
"""
    return html

def main():
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
                title = get_child_text(item, "title")
                link = get_child_text(item, "link")
                summary = get_child_text(item, "description")
                date = get_child_text(item, "pubDate")

                stories.append({
                    "category": feed["category"],
                    "source": feed["source"],
                    "title": title,
                    "link": link,
                    "summary": summary[:220],
                    "date": date
                })

        except Exception as error:
            stories.append({
                "category": feed["category"],
                "source": feed["source"],
                "title": "Could not fetch feed",
                "link": feed["url"],
                "summary": str(error),
                "date": ""
            })

    html = build_html(stories)

    with open("/opt/kenya-news/index.html", "w", encoding="utf-8") as file:
        file.write(html)

if __name__ == "__main__":
    main()
