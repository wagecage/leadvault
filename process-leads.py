#!/usr/bin/env python3
"""Process raw Google Maps JSON into clean CSV lead lists + preview versions."""
import json
import csv
import os
import sys

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
PREVIEW_DIR = os.path.join(os.path.dirname(__file__), "previews")
PREVIEW_ROWS = 10

NICHES = {
    "dentists": "Dentists — Top US Cities",
    "plumbers": "Plumbers — Top US Cities",
    "realtors": "Real Estate Agents — Top US Cities",
    "restaurants": "Restaurants — Top US Cities",
    "gyms": "Gyms & Fitness — Top US Cities",
}

CSV_HEADERS = [
    "Business Name",
    "Category",
    "Address",
    "City",
    "State",
    "Postal Code",
    "Phone",
    "Website",
    "Rating",
    "Review Count",
    "Latitude",
    "Longitude",
]

def extract_row(place):
    loc = place.get("location", {}) or {}
    return {
        "Business Name": place.get("title", ""),
        "Category": place.get("categoryName", ""),
        "Address": place.get("address", ""),
        "City": place.get("city", ""),
        "State": place.get("state", ""),
        "Postal Code": place.get("postalCode", ""),
        "Phone": place.get("phone", ""),
        "Website": place.get("website", ""),
        "Rating": place.get("totalScore", ""),
        "Review Count": place.get("reviewsCount", ""),
        "Latitude": loc.get("lat", ""),
        "Longitude": loc.get("lng", ""),
    }

def extract_json_from_raw(content):
    """Extract JSON array from mcporter raw output.

    The raw output is a JS object with a content array containing text blocks.
    The first text block contains the actual JSON array of places.
    """
    import re
    # Strategy 1: Content starts with [ (pure JSON)
    if content.lstrip().startswith("[{"):
        return json.loads(content)

    # Strategy 2: Find the JSON array embedded in text field
    # Look for the pattern: text: '[{...}]'
    # The JSON is between the first [{ and the matching }]
    # Find first occurrence of [{"title"
    marker = '[{"title"'
    start = content.find(marker)
    if start >= 0:
        # Find the end of this JSON array - look for }]
        # We need to find the right closing bracket
        depth = 0
        i = start
        while i < len(content):
            if content[i] == '[':
                depth += 1
            elif content[i] == ']':
                depth -= 1
                if depth == 0:
                    return json.loads(content[start:i+1])
            i += 1

    # Strategy 3: Try regex for any JSON array
    match = re.search(r'\[\s*\{.*?\}\s*\]', content, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass

    return None

def process_niche(niche_key):
    raw_file = os.path.join(DATA_DIR, f"{niche_key}-raw.json")
    if not os.path.exists(raw_file):
        print(f"  SKIP: {raw_file} not found")
        return 0

    with open(raw_file) as f:
        content = f.read().strip()

    data = extract_json_from_raw(content)
    if data is None:
        print(f"  ERROR: Could not parse {raw_file}")
        return 0

    # Deduplicate by placeId
    seen = set()
    rows = []
    for place in data:
        pid = place.get("placeId", "")
        if pid and pid in seen:
            continue
        seen.add(pid)
        if place.get("permanentlyClosed"):
            continue
        rows.append(extract_row(place))

    # Sort by review count descending
    rows.sort(key=lambda r: int(r["Review Count"] or 0), reverse=True)

    # Write full CSV
    full_path = os.path.join(DATA_DIR, f"{niche_key}-leads.csv")
    with open(full_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows)

    # Write preview CSV
    preview_path = os.path.join(PREVIEW_DIR, f"{niche_key}-preview.csv")
    with open(preview_path, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        writer.writeheader()
        writer.writerows(rows[:PREVIEW_ROWS])

    print(f"  {niche_key}: {len(rows)} leads → {full_path}")
    print(f"  {niche_key}: {min(len(rows), PREVIEW_ROWS)} preview → {preview_path}")
    return len(rows)

def main():
    os.makedirs(PREVIEW_DIR, exist_ok=True)
    total = 0
    stats = {}
    for niche_key, niche_name in NICHES.items():
        print(f"Processing {niche_name}...")
        count = process_niche(niche_key)
        total += count
        stats[niche_key] = count

    print(f"\nTotal leads processed: {total}")
    # Write stats
    with open(os.path.join(DATA_DIR, "stats.json"), "w") as f:
        json.dump(stats, f, indent=2)
    return stats

if __name__ == "__main__":
    main()
