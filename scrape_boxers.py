"""
Boxer Wikipedia scraper
Run from the project root:  python scrape_boxers.py

Requires: pip install requests beautifulsoup4 python-dotenv
"""

import os
import re
import sys
import time

import requests
from bs4 import BeautifulSoup

# ── Load .env then bootstrap Flask app ────────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from website import create_app, db
from website.models import Boxer

# ── Boxer list (Wikipedia page titles) ────────────────────────────────────────
BOXER_PAGES = [
    # Heavyweight
    "Muhammad Ali",
    "Joe Louis",
    "Mike Tyson",
    "Lennox Lewis",
    "Evander Holyfield",
    "Larry Holmes",
    "Joe Frazier",
    "George Foreman",
    "Wladimir Klitschko",
    "Anthony Joshua",
    "Sonny Liston",
    "Rocky Marciano",
    "Vitali Klitschko",
    # Cruiserweight / Light Heavyweight
    "Oleksandr Usyk",
    "David Haye",
    "Roy Jones Jr.",
    "Archie Moore",
    "Sergey Kovalev",
    # Super Middleweight
    "Andre Ward",
    "Joe Calzaghe",
    "James DeGale",
    # Middleweight
    "Sugar Ray Robinson",
    "Marvin Hagler",
    "Carlos Monzon",
    "Gennady Golovkin",
    "Jake LaMotta",
    # Super Welterweight / Welterweight
    "Canelo Alvarez",
    "Sugar Ray Leonard",
    "Floyd Mayweather Jr.",
    "Manny Pacquiao",
    "Oscar De La Hoya",
    "Thomas Hearns",
    # Super Lightweight / Lightweight
    "Aaron Pryor",
    "Roberto Duran",
    "Vasyl Lomachenko",
    "Devin Haney",
    "Alexis Arguello",
    # Featherweight
    "Salvador Sanchez",
    "Willie Pep",
    "Marco Antonio Barrera",
    "Erik Morales",
    # Bantamweight / Flyweight
    "Nonito Donaire",
    "Eder Jofre",
    "Roman Gonzalez (boxer)",
]

WIKI_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "BoxingEducationSite/1.0 (educational project; python-requests)"}


# ── Helpers ───────────────────────────────────────────────────────────────────

def clean(text: str) -> str:
    """Strip citation markers, excess whitespace, and stray brackets."""
    text = re.sub(r'\[[\d\w\s]+\]', '', text)   # [1], [a], [note 1]
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def get_infobox_value(info: dict, *keys: str):
    """Return the first matching value from the infobox dict (case-insensitive)."""
    for key in keys:
        val = info.get(key.lower())
        if val:
            return val
    return None


def parse_int(text) -> int:
    """Extract the first integer from a string."""
    if not text:
        return 0
    m = re.search(r'\d+', str(text))
    return int(m.group()) if m else 0


def scrape_boxer(page_name: str) -> dict | None:
    params = {
        "action": "parse",
        "page": page_name,
        "prop": "text",
        "format": "json",
        "redirects": True,
    }
    try:
        resp = requests.get(WIKI_API, params=params, headers=HEADERS, timeout=20)
        resp.raise_for_status()
    except requests.RequestException as exc:
        print(f"  Network error: {exc}")
        return None

    data = resp.json()
    if "error" in data:
        print(f"  API error: {data['error'].get('info')}")
        return None

    resolved_title = data["parse"].get("title", page_name)
    wiki_url = f"https://en.wikipedia.org/wiki/{resolved_title.replace(' ', '_')}"

    soup = BeautifulSoup(data["parse"]["text"]["*"], "html.parser")

    # ── Find infobox ──────────────────────────────────────────────────────────
    infobox = soup.find("table", class_=re.compile(r"\binfobox\b"))
    if not infobox:
        print("  No infobox found — skipping")
        return None

    # ── Boxer name ────────────────────────────────────────────────────────────
    name = resolved_title
    caption = infobox.find("caption")
    if caption:
        name = clean(caption.get_text())
    else:
        th_title = infobox.find("th", attrs={"colspan": True})
        if th_title:
            candidate = clean(th_title.get_text())
            if candidate:
                name = candidate

    # ── Image ─────────────────────────────────────────────────────────────────
    image_url = None
    img_tag = infobox.find("img")
    if img_tag and img_tag.get("src"):
        src = img_tag["src"]
        image_url = ("https:" + src) if src.startswith("//") else src

    # ── Build key→value dict from infobox rows ────────────────────────────────
    info: dict[str, str] = {}
    for row in infobox.find_all("tr"):
        th = row.find("th")
        td = row.find("td")
        if th and td:
            key = clean(th.get_text()).lower()
            val = clean(td.get_text(separator=" "))
            if key and val:
                info[key] = val

    # ── Extract individual fields ─────────────────────────────────────────────
    # Nickname
    nickname_raw = get_infobox_value(info, "nicknames", "nickname", "also known as", "known as")
    nickname = None
    if nickname_raw:
        # Take just the first nickname
        nickname = re.split(r'[\n|,]', nickname_raw)[0].strip().strip('"\'')
        nickname = nickname[:150] if len(nickname) > 150 else nickname

    # Hometown — parse from "Born" row (date, city, country)
    hometown = None
    born_val = get_infobox_value(info, "born", "birth place", "birthplace")
    if born_val:
        parts = [p.strip() for p in re.split(r'[,\n]', born_val) if p.strip()]
        # Skip date-like parts (contain digits at the start)
        loc_parts = [p for p in parts if not re.match(r'^\d', p)]
        if loc_parts:
            hometown = ", ".join(loc_parts[-2:])[:200]

    nationality = get_infobox_value(info, "nationality", "citizenship")
    if nationality:
        nationality = nationality[:100]

    weight_class = get_infobox_value(info, "weight", "weight class", "division", "class")
    if weight_class:
        weight_class = weight_class[:100]

    stance = get_infobox_value(info, "stance")
    if stance:
        # Strip extra notes like "Orthodox (later switched...)"
        stance = re.split(r'[\(\[]', stance)[0].strip()[:50]

    years_active = get_infobox_value(info, "years active", "active", "career")
    if years_active:
        years_active = years_active[:50]

    # Record — try direct infobox fields first
    record_wins    = parse_int(get_infobox_value(info, "wins"))
    record_losses  = parse_int(get_infobox_value(info, "losses"))
    record_draws   = parse_int(get_infobox_value(info, "draws"))
    wins_by_ko     = parse_int(get_infobox_value(info, "wins by ko", "ko wins", "knockouts", "kos"))
    no_contests    = parse_int(get_infobox_value(info, "no contests", "no contest", "nc"))

    # Fallback: scan for a "W–L–D" style string anywhere on the page
    if record_wins == 0:
        record_text = soup.get_text()
        m = re.search(r'(\d+)\s*[–\-]\s*(\d+)\s*[–\-]\s*(\d+)', record_text)
        if m:
            record_wins   = int(m.group(1))
            record_losses = int(m.group(2))
            record_draws  = int(m.group(3))

    # ── Titles: look for a "championships" or "accomplishments" section ───────
    titles = []
    for heading in soup.find_all(["h2", "h3", "h4"]):
        heading_text = heading.get_text().lower()
        if any(w in heading_text for w in ["championship", "title", "accomplishment", "honour", "honor", "career"]):
            sib = heading.find_next_sibling()
            while sib and sib.name not in ["h2", "h3"]:
                if sib.name in ["ul", "ol"]:
                    for li in sib.find_all("li", recursive=False):
                        item = clean(li.get_text())
                        if item and len(item) < 200 and item not in titles:
                            titles.append(item)
                sib = sib.find_next_sibling()
            if titles:
                break

    titles_str = "|".join(titles[:12])

    return {
        "name":          name,
        "nickname":      nickname,
        "hometown":      hometown,
        "nationality":   nationality,
        "weight_class":  weight_class,
        "stance":        stance,
        "years_active":  years_active,
        "record_wins":   record_wins,
        "record_losses": record_losses,
        "record_draws":  record_draws,
        "wins_by_ko":    wins_by_ko,
        "no_contests":   no_contests,
        "titles":        titles_str,
        "image_url":     image_url,
        "wikipedia_url": wiki_url,
    }


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        added = 0
        skipped = 0
        failed = 0

        for page_name in BOXER_PAGES:
            print(f"\nScraping: {page_name} …")

            # Quick duplicate check by the page name first
            if Boxer.query.filter(Boxer.wikipedia_url.like(f"%{page_name.replace(' ', '_')}")).first():
                print("  Already in DB — skipping")
                skipped += 1
                continue

            data = scrape_boxer(page_name)
            if not data:
                failed += 1
                continue

            # Second duplicate check using the resolved name
            if Boxer.query.filter_by(name=data["name"]).first():
                print(f"  '{data['name']}' already in DB — skipping")
                skipped += 1
                continue

            boxer = Boxer(**data)
            db.session.add(boxer)
            db.session.commit()
            added += 1
            print(
                f"  Saved: {data['name']}"
                f"  [{data.get('weight_class', '?')}]"
                f"  {data['record_wins']}-{data['record_losses']}-{data['record_draws']}"
            )

            time.sleep(1.0)   # be polite to Wikipedia

        total = Boxer.query.count()
        print(f"\n── Done ──────────────────────────────────────")
        print(f"  Added: {added}  |  Skipped: {skipped}  |  Failed: {failed}")
        print(f"  Total boxers in database: {total}")


if __name__ == "__main__":
    main()
