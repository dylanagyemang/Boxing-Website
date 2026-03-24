"""
clean_boxer_names.py
One-time script to repair dirty boxer names already stored in the database.

Dirt sources:
  - Honorifics concatenated to names   e.g. "Ricky HattonMBE", "SirHenry CooperOBE KSG"
  - Non-Latin script annotations       e.g. "Junto Nakatani中谷潤人", "Khaosai Galaxy เขาทราย..."
  - Quoted ring names                  e.g. 'Ted "Kid" Lewis'
  - Special Latin letters outside our chosen spelling  e.g. "Lovemore Nḓou"
  - Name-order differences             e.g. "Chang Jung-koo" (Korean convention)
  - Real name vs ring name             e.g. "Gabriel Elorde" instead of "Flash Elorde"

Run from the project root:
    python clean_boxer_names.py
"""

import os, re, sys, unicodedata, difflib

if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

from dotenv import load_dotenv
load_dotenv()
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from website import create_app, db
from website.models import Boxer
from scrape_boxers import BOXER_PAGES


# ── Build canonical name list from BOXER_PAGES ────────────────────────────────
# Strip disambiguation suffixes e.g. "(boxer)", "(Argentine boxer)"
def strip_disambiguation(page_name: str) -> str:
    return re.sub(r'\s*\([^)]+\)\s*$', '', page_name).strip()

CANONICAL_NAMES: list[str] = [strip_disambiguation(p) for p in BOXER_PAGES]


# ── Manual overrides ──────────────────────────────────────────────────────────
# Applied AFTER regex cleaning. Keys are the regex-cleaned names (or close to
# them); values are the correct canonical names.
MANUAL_OVERRIDES: dict[str, str] = {
    # Korean name-order convention stored as family-name-first
    "Chang Jung-koo":           "Jung-Koo Chang",
    # Real name stored instead of ring name
    "Gabriel Elorde":           "Flash Elorde",
    "Jacob Matlala":            "Baby Jake Matlala",
    # Wikipedia uses "Robert" but we list him as "Bob"
    "Robert Fitzsimmons":       "Bob Fitzsimmons",
    # Different Romanisation of Ukrainian name
    "Vasiliy Lomachenko":       "Vasyl Lomachenko",
    # Venda special character ḓ → d
    "Lovemore Nḓou":            "Lovemore Ndou",
    # K vs Kh difference
    "Khaokor Galaxy":           "Kaokor Galaxy",
    # Wikipedia infobox caption includes birth-name annotation
    "Vasiliy LomachenkoВасиль Ломаченко": "Vasyl Lomachenko",
}


# ── Regex patterns ────────────────────────────────────────────────────────────

# Post-nominal letters that may appear with or without a leading space
_POSTNOMINALS = (
    "OBE", "MBE", "CBE", "KBE", "DBE", "GBE",
    "AM", "QC", "PP", "MON", "KSG", "BEM", "CHE",
)
_PN_PATTERN = r'(?:' + '|'.join(_POSTNOMINALS) + r')'

# Matches one or more post-nominals at the END of the string (may be concatenated)
POSTNOMINAL_SUFFIX_RE = re.compile(
    r'(' + _PN_PATTERN + r')(\s+' + _PN_PATTERN + r')*\s*$',
    re.IGNORECASE,
)

# "Sir" / "Dame" prefix, possibly concatenated with the first name
HONORIFIC_PREFIX_RE = re.compile(r'^(Sir|Dame)\s*', re.IGNORECASE)

# Characters outside Latin Unicode blocks and common punctuation.
# Keeps:  Basic Latin (0000-007F)
#         Latin-1 Supplement (0080-00FF)
#         Latin Extended-A (0100-017F)
#         Latin Extended-B (0180-024F)
#         Latin Extended Additional (1E00-1EFF)  — e.g. ḓ
NON_LATIN_RE = re.compile(r'[^\u0000-\u024F\u1E00-\u1EFF\s]')


def regex_clean(name: str) -> str:
    """Strip honorifics, non-Latin annotations, and quotes from a name."""
    # 1. Strip leading "Sir" / "Dame" (may be directly concatenated)
    name = HONORIFIC_PREFIX_RE.sub('', name)
    # 2. Strip trailing post-nominal letters (may be directly concatenated)
    name = POSTNOMINAL_SUFFIX_RE.sub('', name)
    # 3. Strip any remaining non-Latin Unicode blocks (CJK, Thai, Cyrillic, etc.)
    name = NON_LATIN_RE.sub('', name)
    # 4. Remove double-quotes (e.g. Ted "Kid" Lewis → Ted Kid Lewis)
    name = name.replace('"', '')
    # 5. Collapse whitespace
    name = re.sub(r'\s+', ' ', name).strip()
    return name


# ── Normalisation for fuzzy / exact comparison ────────────────────────────────

def normalize(s: str) -> str:
    """Lowercase, decompose accents, keep only a-z digits and spaces."""
    # Replace hyphens with spaces so "Jung-Koo" == "Jung Koo" in comparison
    s = re.sub(r'[-–—]', ' ', s)
    # NFD decomposition splits accented chars into base + combining mark
    s = unicodedata.normalize('NFD', s)
    # Drop combining marks (accents)
    s = ''.join(c for c in s if unicodedata.category(c) != 'Mn')
    s = s.lower()
    # Keep only alphanumeric and spaces
    s = re.sub(r'[^a-z0-9\s]', '', s)
    return re.sub(r'\s+', ' ', s).strip()


# Build a {normalized_key: canonical_name} lookup
NORM_CANONICAL: dict[str, str] = {normalize(c): c for c in CANONICAL_NAMES}
CANONICAL_NORMS: list[str] = list(NORM_CANONICAL.keys())


def find_canonical(cleaned_name: str) -> str | None:
    """Return the canonical name for a cleaned name, or None if no match."""
    norm = normalize(cleaned_name)

    # 1. Exact match on normalized key
    if norm in NORM_CANONICAL:
        return NORM_CANONICAL[norm]

    # 2. Fuzzy match on normalized names (cutoff=0.80 to avoid wrong matches)
    matches = difflib.get_close_matches(norm, CANONICAL_NORMS, n=1, cutoff=0.80)
    if matches:
        return NORM_CANONICAL[matches[0]]

    return None


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    app = create_app()
    with app.app_context():
        boxers = Boxer.query.order_by(Boxer.name).all()
        changed = 0

        for boxer in boxers:
            original = boxer.name

            # Step 1 — apply regex cleaning (honorifics, non-Latin, quotes)
            step1 = regex_clean(original)

            # Step 2 — check manual overrides (keyed by regex-cleaned name)
            if step1 in MANUAL_OVERRIDES:
                new_name = MANUAL_OVERRIDES[step1]
            # Also check the raw original against overrides (covers cases where
            # the raw name itself is the key, e.g. names with special Latin chars)
            elif original in MANUAL_OVERRIDES:
                new_name = MANUAL_OVERRIDES[original]
            else:
                # Step 3 — try to match to a canonical BOXER_PAGES name
                canonical = find_canonical(step1)
                new_name = canonical if canonical else step1

            if new_name != original:
                print(f"  BEFORE: {original!r}")
                print(f"  AFTER:  {new_name!r}")
                print()
                boxer.name = new_name
                changed += 1

        db.session.commit()
        print(f"── Done ──────────────────────────────────────")
        print(f"  Updated {changed} of {len(boxers)} boxers.")


if __name__ == "__main__":
    main()
