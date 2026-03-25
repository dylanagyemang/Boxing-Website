"""
Patch script — backfill wins_by_ko for all boxers in the database.

Wikipedia's boxer infobox renders the KO row header as "KO" (not "KOs" /
"knockouts" / "wins by ko"), so the original scraper's key lookup missed it.
This script also handles infoboxes where the record section uses <td><td>
pairs instead of <th><td> pairs, which the original scraper skipped entirely.

Run from the project root:
    python patch_ko_wins.py
"""

import os
import re
import sys
import time

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from website import create_app, db
from website.models import Boxer

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS  = {"User-Agent": "BoxingEducationSite/1.0 (educational project; python-requests)"}

# All key labels Wikipedia uses for the KO wins row (case-insensitive after .lower())
KO_KEYS = {"ko", "kos", "knockouts", "ko wins", "wins by ko", "by ko"}


def clean(text: str) -> str:
    text = re.sub(r'\[[\d\w\s]+\]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def parse_int(text) -> int:
    if not text:
        return 0
    m = re.search(r'\d+', str(text))
    return int(m.group()) if m else 0


def fetch_ko_wins(wikipedia_url: str) -> int | None:
    """
    Fetch the Wikipedia page for the boxer and return their KO wins count,
    or None if the page could not be fetched / parsed.

    Tries three strategies in order:
      1. th/td pairs in the infobox  (standard infobox rows)
      2. td/td pairs in the infobox  (record sub-table rows)
      3. Regex on the full page text as a last resort
    """
    # Derive the page title from the URL
    page_title = wikipedia_url.rstrip('/').split('/wiki/')[-1].replace('_', ' ')

    params = {
        "action": "parse",
        "page":   page_title,
        "prop":   "text",
        "format": "json",
        "redirects": True,
    }
    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"    Network error: {exc}")
        return None

    data = resp.json()
    if "error" in data:
        print(f"    API error: {data['error'].get('info')}")
        return None

    soup = BeautifulSoup(data["parse"]["text"]["*"], "html.parser")
    infobox = soup.find("table", class_=re.compile(r"\binfobox\b"))
    if not infobox:
        return None

    # ── Strategy 1: <th> label + <td> value ──────────────────────────────────
    for row in infobox.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            key = clean(th.get_text()).lower()
            if key in KO_KEYS:
                val = parse_int(clean(td.get_text()))
                if val > 0:
                    return val

    # ── Strategy 2: two <td> cells — first is the label, second is the value ─
    for row in infobox.find_all("tr"):
        tds = row.find_all("td")
        if len(tds) >= 2:
            label = clean(tds[0].get_text()).lower()
            if label in KO_KEYS:
                val = parse_int(clean(tds[1].get_text()))
                if val > 0:
                    return val

    # ── Strategy 3: regex scan of full infobox text ───────────────────────────
    # Looks for patterns like "KO  37" or "KOs: 37" anywhere in the infobox
    infobox_text = clean(infobox.get_text(separator=" "))
    m = re.search(r'\bKOs?\b[\s:–-]*(\d+)', infobox_text, re.IGNORECASE)
    if m:
        val = int(m.group(1))
        if val > 0:
            return val

    return 0   # Page fetched but no KO data found


def main():
    app = create_app()
    with app.app_context():
        boxers = Boxer.query.filter_by(wins_by_ko=0).all()
        total  = len(boxers)
        print(f"Boxers with wins_by_ko = 0: {total}\n")

        updated = 0
        not_found = 0
        failed = 0

        for boxer in boxers:
            if not boxer.wikipedia_url:
                print(f"  [{boxer.name}] — no Wikipedia URL, skipping")
                failed += 1
                continue

            print(f"  Fetching: {boxer.name} …", end=" ", flush=True)
            ko = fetch_ko_wins(boxer.wikipedia_url)

            if ko is None:
                print("FETCH ERROR")
                failed += 1
            elif ko == 0:
                print("not found (0)")
                not_found += 1
            else:
                boxer.wins_by_ko = ko
                db.session.commit()
                updated += 1
                print(f"{ko} KOs ✓")

            time.sleep(0.8)

        print(f"\n── Done ──────────────────────────────────────────────")
        print(f"  Updated:   {updated}")
        print(f"  Not found: {not_found}  (stays 0)")
        print(f"  Errors:    {failed}")
        print(f"  Total processed: {total}")


if __name__ == "__main__":
    main()
