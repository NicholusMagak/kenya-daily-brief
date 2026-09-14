#!/bin/bash

set -e

APP_DIR=/opt/kenya-news

echo "Starting Kenya news update at $(date)"

cd "$APP_DIR"

# The API key. Root-owned, chmod 600, never in git.
# Create with:  printf 'ANTHROPIC_API_KEY=sk-ant-...\n' | sudo tee /etc/kenya-news.env
if [ -f /etc/kenya-news.env ]; then
    set -a
    . /etc/kenya-news.env
    set +a
fi

# Ubuntu 26.04 enforces PEP 668, so the Anthropic SDK cannot go into system
# Python. Created once with:  python3 -m venv /opt/kenya-news/.venv
PYTHON="$APP_DIR/.venv/bin/python3"
if [ ! -x "$PYTHON" ]; then
    echo "venv missing at $PYTHON — falling back to system python3 (no labelling)"
    PYTHON=python3
fi

# 1. Fetch feeds, store new articles, render with whatever labels exist.
"$PYTHON" build_news.py

# 2. Label anything new. Non-fatal: a labelling failure must not take the site
#    down, so the page still publishes with the labels it already had.
if [ -n "$ANTHROPIC_API_KEY" ]; then
    "$PYTHON" label.py || echo "labelling failed — publishing with existing labels"

    # 3. Re-render so today's new labels actually appear on the page.
    "$PYTHON" build_news.py
else
    echo "ANTHROPIC_API_KEY not set — skipping labelling"
fi

sudo cp "$APP_DIR/index.html" /var/www/html/index.html

echo "Finished Kenya news update at $(date)"
