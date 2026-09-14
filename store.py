#!/usr/bin/env python3
"""SQLite storage for Kenya Daily Brief articles and sentiment labels.

The site used to be stateless: fetch, render, overwrite, forget. That made the
hand-check impossible, because you cannot sample 50 articles from a corpus that
does not exist, and you could never re-run the agreement measurement later.
This module is the corpus.

stdlib only.
"""

import hashlib
import os
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.environ.get(
    "KDB_DB",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "kenya_news.db"),
)

TONES = ("negative", "neutral", "positive")

SCHEMA = """
CREATE TABLE IF NOT EXISTS articles (
    id          TEXT PRIMARY KEY,
    link        TEXT NOT NULL,
    title       TEXT NOT NULL,
    standfirst  TEXT NOT NULL,
    source      TEXT NOT NULL,
    category    TEXT NOT NULL,
    pub_date    TEXT,
    first_seen  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS labels (
    article_id     TEXT NOT NULL,
    subject        TEXT NOT NULL,
    labeller       TEXT NOT NULL,
    subject_type   TEXT NOT NULL,
    tone           TEXT NOT NULL CHECK (tone IN ('negative','neutral','positive')),
    confidence     REAL,
    evidence       TEXT,
    rubric_version TEXT NOT NULL,
    created_at     TEXT NOT NULL,
    PRIMARY KEY (article_id, subject, labeller),
    FOREIGN KEY (article_id) REFERENCES articles(id)
);

CREATE TABLE IF NOT EXISTS label_runs (
    article_id TEXT NOT NULL,
    labeller   TEXT NOT NULL,
    status     TEXT NOT NULL,
    detail     TEXT,
    created_at TEXT NOT NULL,
    PRIMARY KEY (article_id, labeller)
);

CREATE INDEX IF NOT EXISTS idx_labels_labeller ON labels(labeller);
CREATE INDEX IF NOT EXISTS idx_labels_tone ON labels(labeller, tone);
CREATE INDEX IF NOT EXISTS idx_articles_seen ON articles(first_seen);
"""


def now_utc():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def article_id(link):
    """Stable id from the article link.

    The link is the only field the feeds keep stable — titles get edited after
    publication, and re-hashing on a title edit would fork one article into two
    corpus rows with different labels.
    """
    return hashlib.sha256(link.strip().encode("utf-8")).hexdigest()[:16]


def connect(path=None):
    conn = sqlite3.connect(path or DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(SCHEMA)
    return conn


def upsert_article(conn, link, title, standfirst, source, category, pub_date):
    """Insert an article if new. Returns (id, is_new).

    Existing rows are left alone: first_seen must not drift, and re-writing the
    standfirst under labels already computed from the old text would silently
    decouple a label from its evidence.
    """
    aid = article_id(link)
    row = conn.execute("SELECT 1 FROM articles WHERE id = ?", (aid,)).fetchone()
    if row:
        return aid, False
    conn.execute(
        "INSERT INTO articles (id, link, title, standfirst, source, category,"
        " pub_date, first_seen) VALUES (?,?,?,?,?,?,?,?)",
        (aid, link, title, standfirst, source, category, pub_date, now_utc()),
    )
    return aid, True


def save_labels(conn, aid, labels, labeller, rubric_version):
    """Replace this labeller's labels for one article."""
    conn.execute(
        "DELETE FROM labels WHERE article_id = ? AND labeller = ?", (aid, labeller)
    )
    for lab in labels:
        if lab["tone"] not in TONES:
            raise ValueError(f"bad tone {lab['tone']!r} for {aid}")
        conn.execute(
            "INSERT INTO labels (article_id, subject, labeller, subject_type, tone,"
            " confidence, evidence, rubric_version, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (
                aid,
                lab["subject"].strip(),
                labeller,
                lab.get("subject_type", "unknown"),
                lab["tone"],
                lab.get("confidence"),
                lab.get("evidence", ""),
                rubric_version,
                now_utc(),
            ),
        )


def upsert_label(conn, aid, label, labeller, rubric_version):
    """Write ONE (article, entity) label, leaving that article's others alone.

    Distinct from save_labels: the model emits every entity for an article in
    one response, so replacing the set is correct there. The human adjudicates
    one entity at a time, and a sample routinely contains two entities from the
    same article — replacing the set would erase the first when the second is
    recorded.
    """
    if label["tone"] not in TONES:
        raise ValueError(f"bad tone {label['tone']!r} for {aid}")
    conn.execute(
        "INSERT OR REPLACE INTO labels (article_id, subject, labeller,"
        " subject_type, tone, confidence, evidence, rubric_version, created_at)"
        " VALUES (?,?,?,?,?,?,?,?,?)",
        (
            aid,
            label["subject"].strip(),
            labeller,
            label.get("subject_type", "unknown"),
            label["tone"],
            label.get("confidence"),
            label.get("evidence", ""),
            rubric_version,
            now_utc(),
        ),
    )


def record_run(conn, aid, labeller, status, detail=""):
    """Audit row: what happened when we tried to label this article.

    Without this, a refusal and a genuinely entity-free article are
    indistinguishable — both just have no label rows.
    """
    conn.execute(
        "INSERT OR REPLACE INTO label_runs (article_id, labeller, status, detail,"
        " created_at) VALUES (?,?,?,?,?)",
        (aid, labeller, status, detail, now_utc()),
    )


# A run with one of these statuses is final; anything else is retried on the
# next pass. Errors are transient by nature — an expired key, no credit, a
# network blip — and must not permanently retire an article from the queue.
FINAL_STATUSES = ("ok", "refused")


def unlabelled(conn, labeller, limit=None, retry_errors=True):
    """Articles still needing this labeller.

    Excludes articles already labelled or refused. Articles whose last attempt
    errored come back unless retry_errors is False.
    """
    final = FINAL_STATUSES if retry_errors else ("ok", "refused", "error")
    placeholders = ",".join("?" * len(final))
    sql = (
        "SELECT * FROM articles WHERE id NOT IN"
        f" (SELECT article_id FROM label_runs WHERE labeller = ?"
        f"  AND status IN ({placeholders}))"
        " ORDER BY first_seen"
    )
    params = [labeller, *final]
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def labels_for(conn, labeller):
    return conn.execute(
        "SELECT l.*, a.title, a.standfirst, a.link, a.source FROM labels l"
        " JOIN articles a ON a.id = l.article_id WHERE l.labeller = ?"
        " ORDER BY l.article_id, l.subject",
        (labeller,),
    ).fetchall()


def tone_counts(conn, labeller):
    rows = conn.execute(
        "SELECT tone, COUNT(*) n FROM labels WHERE labeller = ? GROUP BY tone",
        (labeller,),
    ).fetchall()
    return {r["tone"]: r["n"] for r in rows}


def stratified_sample(conn, labeller, per_class, seed, exclude_labeller=None):
    """Sample pairs evenly across model-predicted tone.

    Random sampling of this corpus returns mostly neutrals and measures nothing
    about the rare classes, so we sample per stratum and re-weight at scoring
    time (agreement.py --corpus).

    Ordering is by a seeded hash rather than RANDOM() so the same seed returns
    the same 50 pairs — an adjudication interrupted halfway can be resumed
    without silently changing the sample.
    """
    out = []
    for tone in TONES:
        sql = (
            "SELECT l.article_id, l.subject FROM labels l"
            " WHERE l.labeller = ? AND l.tone = ?"
        )
        params = [labeller, tone]
        if exclude_labeller:
            sql += (
                " AND NOT EXISTS (SELECT 1 FROM labels h WHERE h.article_id ="
                " l.article_id AND h.subject = l.subject AND h.labeller = ?)"
            )
            params.append(exclude_labeller)
        rows = conn.execute(sql, params).fetchall()
        rows.sort(
            key=lambda r: hashlib.sha256(
                f"{seed}:{r['article_id']}:{r['subject']}".encode()
            ).hexdigest()
        )
        out.extend((r["article_id"], r["subject"], tone) for r in rows[:per_class])
    return out


def stats(conn):
    a = conn.execute("SELECT COUNT(*) n FROM articles").fetchone()["n"]
    runs = conn.execute(
        "SELECT status, COUNT(*) n FROM label_runs GROUP BY status"
    ).fetchall()
    return {
        "articles": a,
        "model_labels": len(labels_for(conn, "model")),
        "human_labels": len(labels_for(conn, "human")),
        "runs": {r["status"]: r["n"] for r in runs},
    }


def export_csv(conn, out_dir="."):
    """Write the three CSVs agreement.py reads.

    corpus_labels.csv is every model label, not just the sampled ones — the
    scorer needs the full class prior to re-weight the stratified sample.
    """
    import csv

    written = []
    for name, labeller in (("model_labels", "model"), ("human_labels", "human")):
        path = os.path.join(out_dir, f"{name}.csv")
        rows = labels_for(conn, labeller)
        with open(path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.writer(fh)
            writer.writerow(["article_id", "subject", "tone", "confidence"])
            for r in rows:
                writer.writerow(
                    [r["article_id"], r["subject"], r["tone"],
                     "" if r["confidence"] is None else r["confidence"]]
                )
        written.append((path, len(rows)))

    path = os.path.join(out_dir, "corpus_labels.csv")
    rows = labels_for(conn, "model")
    with open(path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["article_id", "subject", "tone"])
        for r in rows:
            writer.writerow([r["article_id"], r["subject"], r["tone"]])
    written.append((path, len(rows)))
    return written


if __name__ == "__main__":
    import sys

    conn = connect()

    if len(sys.argv) > 1 and sys.argv[1] == "export":
        for path, n in export_csv(conn):
            print(f"wrote {path} ({n} rows)")
        conn.close()
        sys.exit(0)

    s = stats(conn)
    print(f"database:      {DB_PATH}")
    print(f"articles:      {s['articles']}")
    print(f"model labels:  {s['model_labels']}")
    print(f"human labels:  {s['human_labels']}")
    if s["runs"]:
        print("label runs:")
        for status, n in sorted(s["runs"].items()):
            print(f"  {status:<10} {n}")
    counts = tone_counts(conn, "model")
    if counts:
        total = sum(counts.values())
        print("model tone distribution:")
        for tone in TONES:
            n = counts.get(tone, 0)
            print(f"  {tone:<9} {n:>5}  {n / total:>6.1%}")
    conn.close()
