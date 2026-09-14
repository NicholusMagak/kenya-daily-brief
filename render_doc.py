#!/usr/bin/env python3
"""Render SENTIMENT.md to a styled HTML page matching the site.

    python3 render_doc.py SENTIMENT.md sentiment.html

Handles the Markdown subset that document actually uses: ATX headings, tables,
blockquotes, fenced code, bullet and numbered lists, horizontal rules, and
inline code/bold/italic. Not a general Markdown implementation — it is
deliberately small, stdlib-only, and covers exactly what is in the source.

Served as a page rather than the raw file because nginx has no type for .md and
would hand the reader a download instead of something to read.
"""

import re
import sys
from html import escape

CSS = """
    body {
      margin: 0;
      font-family: Arial, sans-serif;
      background: #f3f4f6;
      color: #111827;
      line-height: 1.6;
    }
    header {
      background: #111827;
      color: white;
      padding: 20px;
    }
    header h1 { margin: 0; font-size: 24px; }
    header p { margin: 6px 0 0; color: #d1d5db; font-size: 14px; }
    header a { color: #86efac; font-size: 14px; text-decoration: none; }
    header a:hover { text-decoration: underline; }
    main {
      max-width: 780px;
      margin: auto;
      padding: 16px 16px 60px;
    }
    h1 { font-size: 24px; margin-top: 36px; }
    h2 {
      border-left: 5px solid #16a34a;
      padding-left: 10px;
      font-size: 20px;
      margin-top: 34px;
    }
    h3 { font-size: 16px; margin-top: 26px; }
    p, li { color: #374151; font-size: 15px; }
    strong { color: #111827; }
    code {
      background: #e5e7eb;
      border-radius: 4px;
      padding: 1px 5px;
      font-family: Consolas, Monaco, monospace;
      font-size: 13px;
      color: #111827;
    }
    pre {
      background: #111827;
      color: #e5e7eb;
      padding: 14px 16px;
      border-radius: 10px;
      overflow-x: auto;
      font-size: 13px;
      line-height: 1.5;
    }
    pre code { background: none; padding: 0; color: inherit; }
    blockquote {
      margin: 18px 0;
      padding: 12px 18px;
      background: white;
      border-left: 4px solid #16a34a;
      border-radius: 0 10px 10px 0;
      color: #111827;
    }
    blockquote p { margin: 6px 0; font-size: 15px; }
    .table-wrap { overflow-x: auto; margin: 18px 0; }
    table {
      border-collapse: collapse;
      width: 100%;
      background: white;
      border-radius: 10px;
      overflow: hidden;
      font-size: 14px;
    }
    th, td {
      text-align: left;
      padding: 9px 12px;
      border-bottom: 1px solid #e5e7eb;
      vertical-align: top;
    }
    th { background: #111827; color: white; font-size: 13px; }
    tr:last-child td { border-bottom: none; }
    hr { border: none; border-top: 1px solid #d1d5db; margin: 34px 0; }
    footer {
      text-align: center;
      padding: 30px;
      color: #6b7280;
      font-size: 12px;
    }
    footer a { color: #16a34a; }
"""


def inline(text):
    """Inline markup. Input must already be HTML-escaped."""
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?!\*)", r"<em>\1</em>", text)
    return text


def render_table(rows):
    """rows: list of raw '| a | b |' lines, second one being the separator."""
    def cells(line):
        line = line.strip()
        if line.startswith("|"):
            line = line[1:]
        if line.endswith("|"):
            line = line[:-1]
        return [c.strip() for c in line.split("|")]

    head = cells(rows[0])
    body = [cells(r) for r in rows[2:]]

    out = ['<div class="table-wrap"><table>', "<thead><tr>"]
    out += [f"<th>{inline(escape(c))}</th>" for c in head]
    out.append("</tr></thead><tbody>")
    for row in body:
        out.append("<tr>")
        out += [f"<td>{inline(escape(c))}</td>" for c in row]
        out.append("</tr>")
    out.append("</tbody></table></div>")
    return "".join(out)


def render(md):
    lines = md.split("\n")
    out = []
    i = 0
    n = len(lines)

    while i < n:
        line = lines[i]
        stripped = line.strip()

        # fenced code
        if stripped.startswith("```"):
            i += 1
            buf = []
            while i < n and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.append(f"<pre><code>{escape(chr(10).join(buf))}</code></pre>")
            continue

        # table: a pipe row followed by a separator row
        if (
            stripped.startswith("|")
            and i + 1 < n
            and re.fullmatch(r"\|[\s:|-]+\|", lines[i + 1].strip())
        ):
            buf = []
            while i < n and lines[i].strip().startswith("|"):
                buf.append(lines[i])
                i += 1
            out.append(render_table(buf))
            continue

        if not stripped:
            i += 1
            continue

        if stripped.startswith("---") and set(stripped) <= {"-"}:
            out.append("<hr>")
            i += 1
            continue

        m = re.match(r"(#{1,4})\s+(.*)", stripped)
        if m:
            level = len(m.group(1))
            out.append(f"<h{level}>{inline(escape(m.group(2)))}</h{level}>")
            i += 1
            continue

        # blockquote — consecutive '>' lines become one quote
        if stripped.startswith(">"):
            buf = []
            while i < n and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip()[1:].strip())
                i += 1
            # A fully-bold line is a heading within the quote (the example
            # article's headline), so it keeps its own paragraph rather than
            # running into the standfirst that follows it.
            paras, current = [], []
            for x in buf:
                if not x:
                    continue
                if re.fullmatch(r"\*\*.+\*\*", x):
                    if current:
                        paras.append(" ".join(current))
                        current = []
                    paras.append(x)
                else:
                    current.append(x)
            if current:
                paras.append(" ".join(current))
            body = "".join(f"<p>{inline(escape(p))}</p>" for p in paras)
            out.append(f"<blockquote>{body}</blockquote>")
            continue

        # lists — a wrapped continuation line is indented, so fold it in
        m = re.match(r"([-*]|\d+\.)\s+(.*)", stripped)
        if m:
            ordered = not m.group(1) in ("-", "*")
            tag = "ol" if ordered else "ul"
            items = []
            while i < n:
                s = lines[i].strip()
                mm = re.match(r"([-*]|\d+\.)\s+(.*)", s)
                if mm:
                    items.append(mm.group(2))
                    i += 1
                elif s and lines[i].startswith(("  ", "\t")) and items:
                    items[-1] += " " + s
                    i += 1
                else:
                    break
            out.append(f"<{tag}>")
            out += [f"<li>{inline(escape(x))}</li>" for x in items]
            out.append(f"</{tag}>")
            continue

        # paragraph — consecutive plain lines join
        buf = []
        while i < n:
            s = lines[i].strip()
            if (
                not s
                or s.startswith(("#", ">", "|", "```"))
                or re.match(r"([-*]|\d+\.)\s+", s)
                or (s.startswith("---") and set(s) <= {"-"})
            ):
                break
            buf.append(s)
            i += 1
        out.append(f"<p>{inline(escape(' '.join(buf)))}</p>")

    return "\n".join(out)


def page(body, title, subtitle):
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>{escape(title)} — Kenya Daily Brief</title>
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <style>{CSS}</style>
</head>
<body>
  <header>
    <h1>{escape(title)}</h1>
    <p>{escape(subtitle)}</p>
    <a href="/">&larr; Back to Kenya Daily Brief</a>
  </header>
  <main>
{body}
  </main>
  <footer>
    <a href="/">Kenya Daily Brief</a>
  </footer>
</body>
</html>
"""


def main():
    if len(sys.argv) != 3:
        sys.exit("usage: render_doc.py SOURCE.md OUTPUT.html")

    src, dst = sys.argv[1], sys.argv[2]
    with open(src, encoding="utf-8") as fh:
        md = fh.read()

    # The document's own H1 becomes the page header, so drop it from the body.
    md = re.sub(r"\A#\s+.*\n", "", md)

    html = page(
        render(md),
        "The sentiment label definition",
        "How tone is defined, and the rules used to decide it",
    )

    with open(dst, "w", encoding="utf-8") as fh:
        fh.write(html)

    print(f"wrote {dst} ({len(html)} bytes)")


if __name__ == "__main__":
    main()
