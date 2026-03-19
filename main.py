import os
import re
import csv
import json
import time
from typing import Any, Dict, List, Optional, Tuple

import requests

# =========================
# CONFIG
# =========================

API_URL = "https://api.trove.nla.gov.au/v3/result"
TROVE_API_KEY ="Trove_API"

OUT_DIR = "data"
OUT_JSONL = os.path.join(OUT_DIR, "trove_armenia_maps.jsonl")
OUT_CSV = os.path.join(OUT_DIR, "trove_armenia_maps.csv")
STATE_PATH = os.path.join(OUT_DIR, "harvest_state.json")

# This matches what you showed on the website:
# keyword = ARMENIA
# category = Images, Maps & Artefacts -> API category=image
# format = Map
QUERY = "ARMENIA"
CATEGORY = "image"
FORMAT_FILTER = "Map"

MAX_RECORDS = None

PAGE_SIZE = 100
SORTBY = "relevance"
SLEEP_SECONDS = 0.2

# Trove includes for image/work records
INCLUDE = ["workversions", "holdings", "links"]

# =========================
# UTILITIES
# =========================

def norm(value: Any) -> Optional[str]:
    if value is None:
        return None

    if isinstance(value, list):
        cleaned = [norm(v) for v in value]
        cleaned = [v for v in cleaned if v]
        return ", ".join(cleaned) if cleaned else None

    if isinstance(value, dict):
        for key in ["value", "text", "#text", "name", "identifier", "localIdentifier", "callNumber"]:
            if key in value:
                return norm(value[key])
        return None

    s = str(value)
    s = re.sub(r"[\[\]\{\}']", "", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s or None


def ensure_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def to_list(x: Any) -> List[Any]:
    if x is None:
        return []
    return x if isinstance(x, list) else [x]


def load_state() -> dict:
    if os.path.exists(STATE_PATH):
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_state(state: dict) -> None:
    ensure_dir(os.path.dirname(STATE_PATH))
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def append_jsonl(row: dict, path: str) -> None:
    ensure_dir(os.path.dirname(path))
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def get_with_retries(
    url: str,
    params: List[Tuple[str, str]],
    timeout: int = 90,
    max_tries: int = 6
) -> requests.Response:
    last_err = None
    for attempt in range(1, max_tries + 1):
        try:
            return requests.get(url, params=params, timeout=timeout)
        except (
            requests.exceptions.ReadTimeout,
            requests.exceptions.ConnectTimeout,
            requests.exceptions.ConnectionError,
        ) as e:
            last_err = e
            sleep_s = min(60, 2 ** attempt)
            print(f"[retry {attempt}/{max_tries}] timeout/network error, sleeping {sleep_s}s")
            time.sleep(sleep_s)
    raise last_err  # type: ignore


def parse_material(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    t = text.lower()
    if "parchment" in t or "vellum" in t:
        return "parchment"
    if "paper" in t:
        return "paper"
    return None


def extract_dimensions(text: Optional[str]) -> Optional[str]:
    if not text:
        return None

    patterns = [
        r"\b\d+(?:\.\d+)?\s*(?:x|×)\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|in\.?|inch|inches)\b",
        r"\b\d+(?:\.\d+)?\s*(?:cm|mm|m|in\.?|inch|inches)\s*(?:x|×)\s*\d+(?:\.\d+)?\s*(?:cm|mm|m|in\.?|inch|inches)\b",
    ]

    for pat in patterns:
        m = re.search(pat, text, flags=re.IGNORECASE)
        if m:
            return m.group(0).strip()

    return None

# =========================
# TROVE RESPONSE PARSING
# =========================

def find_records(payload: Any) -> List[Dict[str, Any]]:
    try:
        cats = payload.get("category", [])
        if not cats:
            return []
        recs = cats[0].get("records", {})
        works = recs.get("work", [])
        return works if isinstance(works, list) else []
    except Exception:
        return []


def find_next_cursor(payload: Any) -> Optional[str]:
    try:
        cats = payload.get("category", [])
        if not cats:
            return None
        recs = cats[0].get("records", {})
        nxt = recs.get("nextStart")
        if isinstance(nxt, str) and nxt.strip():
            return nxt.strip()
        return None
    except Exception:
        return None

# =========================
# EXTRACTION
# =========================

def extract_work(work: Dict[str, Any]) -> Dict[str, Any]:
    title = norm(work.get("title"))
    date = norm(work.get("issued")) or norm(work.get("date"))

    contributors = to_list(work.get("contributor"))
    creator_values = [norm(c) for c in contributors]
    creator_values = [c for c in creator_values if c]
    creator = ", ".join(creator_values) if creator_values else None

    abstract = norm(work.get("abstract"))
    trove_url = norm(work.get("troveUrl"))

    best_url = trove_url
    for ident in to_list(work.get("identifier")):
        if isinstance(ident, str) and ident.startswith("http"):
            best_url = ident
            break
        if isinstance(ident, dict):
            val = ident.get("value") or ident.get("#text") or ident.get("text")
            if isinstance(val, str) and val.startswith("http"):
                best_url = val
                break

    shelfmark = None
    for h in to_list(work.get("holding")):
        if isinstance(h, dict):
            val = h.get("callNumber") or h.get("localIdentifier")
            shelfmark = norm(val)
            if shelfmark:
                break

    raw_medium = None
    raw_physical = None
    material = None
    dimensions = None

    for ver in to_list(work.get("version")):
        if not isinstance(ver, dict):
            continue
        for rec in to_list(ver.get("record")):
            if not isinstance(rec, dict):
                continue

            m = norm(rec.get("medium"))
            e = norm(rec.get("extent"))
            f = norm(rec.get("format")) or norm(rec.get("physicalDescription")) or norm(rec.get("dimensions"))

            raw_medium = raw_medium or m
            raw_physical = raw_physical or e or f
            material = material or parse_material(m) or parse_material(e) or parse_material(f)
            dimensions = dimensions or extract_dimensions(e) or extract_dimensions(f)

    return {
        "title": title,
        "date_or_period": date,
        "author_or_creator": creator,
        "description_or_abstract": abstract,
        "url_to_original_object": best_url,
        "manuscript_id_or_shelfmark": shelfmark,
        "trove_category": CATEGORY,
        "trove_id": norm(work.get("id") or work.get("@id")),
        "trove_url": trove_url,
    }

# =========================
# HARVEST
# =========================

def harvest() -> int:
    ensure_dir(OUT_DIR)

    seen_ids = set()
    if os.path.exists(OUT_JSONL):
        with open(OUT_JSONL, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line)
                    tid = obj.get("trove_id")
                    if tid:
                        seen_ids.add(tid)
                except Exception:
                    continue

    state = load_state()
    state_key = f"{CATEGORY}::{QUERY}::{FORMAT_FILTER}"
    cursor = state.get(state_key, "*")
    seen_cursors = {cursor}
    harvested = 0

    while True:
        if MAX_RECORDS is not None and harvested >= MAX_RECORDS:
            break

        params: List[Tuple[str, str]] = [
            ("key", TROVE_API_KEY),
            ("encoding", "json"),
            ("category", CATEGORY),
            ("q", QUERY),
            ("reclevel", "full"),
            ("n", str(min(PAGE_SIZE, 100))),
            ("sortby", SORTBY),
            ("s", cursor),
            ("l-format", FORMAT_FILTER),   # THIS is the map filter
        ]

        for inc in INCLUDE:
            params.append(("include", inc))

        r = get_with_retries(API_URL, params=params)

        if r.status_code != 200:
            raise RuntimeError(f"Trove API error {r.status_code}: {r.text[:800]}")

        payload = r.json()
        records = find_records(payload)

        if not records:
            state[state_key] = cursor
            save_state(state)
            break

        for rec in records:
            if MAX_RECORDS is not None and harvested >= MAX_RECORDS:
                break

            row = extract_work(rec)

            tid = row.get("trove_id")
            if tid and tid in seen_ids:
                continue
            if tid:
                seen_ids.add(tid)

            append_jsonl(row, OUT_JSONL)
            harvested += 1

        next_cursor = find_next_cursor(payload)
        if not next_cursor:
            state[state_key] = cursor
            save_state(state)
            break

        if next_cursor in seen_cursors:
            state[state_key] = next_cursor
            save_state(state)
            break

        seen_cursors.add(next_cursor)
        cursor = next_cursor
        state[state_key] = cursor
        save_state(state)

        time.sleep(SLEEP_SECONDS)

    return harvested


def jsonl_to_csv() -> None:
    columns = [
        "title",
        "date_or_period",
        "author_or_creator",
        "description_or_abstract",
        "url_to_original_object",
        "manuscript_id_or_shelfmark",
        "trove_category",
        "trove_id",
        "trove_url",
    ]

    ensure_dir(os.path.dirname(OUT_CSV))

    with open(OUT_JSONL, "r", encoding="utf-8") as fin, open(OUT_CSV, "w", encoding="utf-8", newline="") as fout:
        writer = csv.DictWriter(fout, fieldnames=columns)
        writer.writeheader()
        for line in fin:
            obj = json.loads(line)
            writer.writerow({c: obj.get(c) for c in columns})


def main() -> None:
    if not TROVE_API_KEY:
        raise SystemExit(
            "Missing TROVE_API_KEY.\n"
            "In PyCharm: Run -> Edit Configurations -> Environment variables\n"
            "Add TROVE_API_KEY=your_key_here"
        )

    print("Query:", QUERY)
    print("Category:", CATEGORY)
    print("Format filter:", FORMAT_FILTER)
    print("Max records:", MAX_RECORDS)
    print("Output JSONL:", OUT_JSONL)
    print("Output CSV:", OUT_CSV)
    print()

    total = harvest()
    print(f"Added {total} rows")

    if os.path.exists(OUT_JSONL):
        print("Converting JSONL to CSV...")
        jsonl_to_csv()
        print("Done")
    else:
        print("No JSONL file created")


if __name__ == "__main__":
    main()