"""
Patch script — backfill nationality for all boxers where it is NULL.

Wikipedia boxing infoboxes rarely have an explicit "nationality" row.
This script tries multiple strategies in order:

  1. Explicit infobox fields: "nationality", "citizenship", "country"
  2. The "born" field — last non-date segment is usually the country;
     map country name → demonym using COUNTRY_MAP
  3. Flag icons in the infobox — Wikipedia renders nationality flags as
     img alt text like "Ghana" which we can map to a demonym
  4. The page categories — e.g. "Ghanaian boxers" gives us "Ghanaian"

Run from the project root:
    python patch_nationality.py
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

# Country name / adjective → stored demonym
COUNTRY_MAP = {
    # English-speaking / common
    "united states": "American",
    "u.s.": "American",
    "usa": "American",
    "american": "American",
    "united kingdom": "British",
    "england": "English",
    "english": "English",
    "wales": "Welsh",
    "welsh": "Welsh",
    "scotland": "Scottish",
    "scottish": "Scottish",
    "ireland": "Irish",
    "irish": "Irish",
    "northern ireland": "British",
    "australia": "Australian",
    "australian": "Australian",
    "canada": "Canadian",
    "canadian": "Canadian",
    "new zealand": "New Zealander",
    # Latin America
    "mexico": "Mexican",
    "mexican": "Mexican",
    "puerto rico": "Puerto Rican",
    "puerto rican": "Puerto Rican",
    "cuba": "Cuban",
    "cuban": "Cuban",
    "panama": "Panamanian",
    "panamanian": "Panamanian",
    "nicaragua": "Nicaraguan",
    "nicaraguan": "Nicaraguan",
    "venezuela": "Venezuelan",
    "venezuelan": "Venezuelan",
    "colombia": "Colombian",
    "colombian": "Colombian",
    "argentina": "Argentine",
    "argentine": "Argentine",
    "argentinian": "Argentine",
    "brazil": "Brazilian",
    "brazilian": "Brazilian",
    "uruguay": "Uruguayan",
    "peru": "Peruvian",
    "dominican republic": "Dominican",
    "dominican": "Dominican",
    "haiti": "Haitian",
    "haiti": "Haitian",
    "trinidad": "Trinidadian",
    "trinidad and tobago": "Trinidadian",
    "jamaica": "Jamaican",
    "jamaican": "Jamaican",
    "ecuador": "Ecuadorian",
    # Europe
    "germany": "German",
    "german": "German",
    "france": "French",
    "french": "French",
    "italy": "Italian",
    "italian": "Italian",
    "spain": "Spanish",
    "spanish": "Spanish",
    "sweden": "Swedish",
    "swedish": "Swedish",
    "russia": "Russian",
    "russian": "Russian",
    "ukraine": "Ukrainian",
    "ukrainian": "Ukrainian",
    "kazakhstan": "Kazakhstani",
    "kazakhstani": "Kazakhstani",
    "uzbekistan": "Uzbek",
    "uzbek": "Uzbek",
    "poland": "Polish",
    "polish": "Polish",
    "hungary": "Hungarian",
    "czech republic": "Czech",
    "slovakia": "Slovak",
    "romania": "Romanian",
    "bulgaria": "Bulgarian",
    "croatia": "Croatian",
    "serbia": "Serbian",
    "soviet union": "Soviet",
    "ussr": "Soviet",
    "netherlands": "Dutch",
    "dutch": "Dutch",
    "belgium": "Belgian",
    "denmark": "Danish",
    "norway": "Norwegian",
    "finland": "Finnish",
    # Africa
    "ghana": "Ghanaian",
    "ghanaian": "Ghanaian",
    "nigeria": "Nigerian",
    "nigerian": "Nigerian",
    "south africa": "South African",
    "south african": "South African",
    "kenya": "Kenyan",
    "kenya": "Kenyan",
    "uganda": "Ugandan",
    "ugandan": "Ugandan",
    "zambia": "Zambian",
    "zimbabwe": "Zimbabwean",
    "cameroon": "Cameroonian",
    "cameroon": "Cameroonian",
    "congo": "Congolese",
    "democratic republic of the congo": "Congolese",
    "ivory coast": "Ivorian",
    "côte d'ivoire": "Ivorian",
    "tanzania": "Tanzanian",
    "ethiopia": "Ethiopian",
    "morocco": "Moroccan",
    "egypt": "Egyptian",
    "senegal": "Senegalese",
    # Asia
    "japan": "Japanese",
    "japanese": "Japanese",
    "philippines": "Filipino",
    "filipino": "Filipino",
    "thailand": "Thai",
    "thai": "Thai",
    "south korea": "South Korean",
    "korea": "South Korean",
    "china": "Chinese",
    "chinese": "Chinese",
    "indonesia": "Indonesian",
    "vietnam": "Vietnamese",
    "india": "Indian",
    "indian": "Indian",
    "bangladesh": "Bangladeshi",
    "pakistan": "Pakistani",
    # Middle East / Central Asia
    "iran": "Iranian",
    "iraq": "Iraqi",
    "turkey": "Turkish",
    "turkish": "Turkish",
    "israel": "Israeli",
    "azerbaijan": "Azerbaijani",
    "georgia": "Georgian",
    "armenia": "Armenian",
}


def clean(text: str) -> str:
    text = re.sub(r'\[[\d\w\s]+\]', '', text)
    text = re.sub(r'\s+', ' ', text)
    return text.strip()


def map_to_demonym(raw: str) -> str | None:
    """Return a stored demonym for a raw country/nationality string, or None."""
    key = raw.lower().strip().rstrip('.')
    # Direct lookup
    if key in COUNTRY_MAP:
        return COUNTRY_MAP[key]
    # Try each word in the string (handles "American (born in Mexico)" etc.)
    for word in re.split(r'[\s,/]+', key):
        if word in COUNTRY_MAP:
            return COUNTRY_MAP[word]
    return None


def fetch_nationality(wikipedia_url: str) -> str | None:
    page_title = wikipedia_url.rstrip('/').split('/wiki/')[-1].replace('_', ' ')

    # Fetch both parsed text and categories in one call
    params = {
        "action":  "parse",
        "page":    page_title,
        "prop":    "text|categories",
        "format":  "json",
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

    if infobox:
        # Build th→td and td→td key/value maps from the infobox
        info: dict[str, str] = {}
        for row in infobox.find_all("tr"):
            th = row.find("th")
            td = row.find("td")
            if th and td:
                info[clean(th.get_text()).lower()] = clean(td.get_text(separator=" "))
            else:
                tds = row.find_all("td")
                if len(tds) >= 2:
                    info[clean(tds[0].get_text()).lower()] = clean(tds[1].get_text(separator=" "))

        # ── Strategy 1: explicit nationality / citizenship fields ─────────────
        for field in ("nationality", "citizenship", "country", "born in", "origin"):
            val = info.get(field)
            if val:
                dem = map_to_demonym(val)
                if dem:
                    return dem

        # ── Strategy 2: parse country from the "born" / "birthplace" field ───
        for field in ("born", "birth place", "birthplace", "place of birth"):
            val = info.get(field)
            if val:
                # Split by comma/newline, skip date-like segments, take the last part
                parts = [p.strip() for p in re.split(r'[,\n]', val) if p.strip()]
                loc_parts = [p for p in parts if not re.match(r'^\d', p)]
                for part in reversed(loc_parts):
                    dem = map_to_demonym(part)
                    if dem:
                        return dem

        # ── Strategy 3: flag icon alt text in the infobox ────────────────────
        for img in infobox.find_all("img"):
            alt = img.get("alt", "")
            dem = map_to_demonym(alt)
            if dem:
                return dem

    # ── Strategy 4: page categories — e.g. "Ghanaian boxers" ─────────────────
    categories = [c.get("*", "") for c in data["parse"].get("categories", [])]
    for cat in categories:
        cat_clean = cat.replace("_", " ").lower()
        # "ghanaian boxers", "american boxers", "mexican boxers", etc.
        m = re.match(r'^(.+?)\s+boxers', cat_clean)
        if m:
            dem = map_to_demonym(m.group(1))
            if dem:
                return dem

    return None


def main():
    app = create_app()
    with app.app_context():
        boxers = Boxer.query.filter(Boxer.nationality.is_(None)).order_by(Boxer.name).all()
        total  = len(boxers)
        print(f"Boxers with no nationality: {total}\n")

        updated   = 0
        not_found = 0
        failed    = 0

        for boxer in boxers:
            if not boxer.wikipedia_url:
                print(f"  [{boxer.name}] — no Wikipedia URL, skipping")
                failed += 1
                continue

            print(f"  {boxer.name} …", end=" ", flush=True)
            nat = fetch_nationality(boxer.wikipedia_url)

            if nat is None:
                print("FETCH ERROR")
                failed += 1
            elif nat == "":
                print("not found")
                not_found += 1
            else:
                boxer.nationality = nat
                db.session.commit()
                updated += 1
                print(nat)

            time.sleep(0.8)

        print(f"\n── Done ──────────────────────────────────────────────")
        print(f"  Updated:   {updated}")
        print(f"  Not found: {not_found}")
        print(f"  Errors:    {failed}")
        print(f"  Total processed: {total}")


if __name__ == "__main__":
    main()
