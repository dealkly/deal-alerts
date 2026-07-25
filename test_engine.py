import requests
from bs4 import BeautifulSoup
import csv
import time
import random
import re
import os
import json

# ------------------ CONFIG ------------------
TODAY_CSV = "books_today.csv"
YESTERDAY_CSV = "books_yesterday.csv"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Cache-Control": "max-age=0",
}

# --------------------------------------------

# Step 1: Rotate CSV files (so pipeline won't break)
if os.path.exists(TODAY_CSV):
    if os.path.exists(YESTERDAY_CSV):
        os.remove(YESTERDAY_CSV)
    os.rename(TODAY_CSV, YESTERDAY_CSV)

# Step 2: Warm up session
session = requests.Session()
session.headers.update(HEADERS)

print("Warming up session (eBay homepage)...")
try:
    session.get("https://www.ebay.com", timeout=15)
    time.sleep(random.uniform(1, 2))
except Exception as e:
    print(f"Warm‑up error (continuing): {e}")

# Step 3: Deep‑inspect only the laptops category
category = "laptops"
url = "https://www.ebay.com/sch/i.html?_nkw=laptop&_sop=15&rt=nc&LH_BIN=1"
print(f"Deep‑inspecting category: {category}")
try:
    response = session.get(url, timeout=15)
    soup = BeautifulSoup(response.text, "html.parser")

    # Print a large chunk of the HTML to see what's really there
    print("----- PAGE HTML SNIPPET (first 2500 chars) -----")
    print(response.text[:2500])
    print("----- END SNIPPET -----")

    # Check for JSON-LD explicitly
    json_scripts = soup.find_all("script", type="application/ld+json")
    print(f"Found {len(json_scripts)} JSON-LD script(s)")
    for i, script in enumerate(json_scripts):
        print(f"JSON-LD block {i}: {script.string[:300] if script.string else '(empty)'}...")

    # List all CSS classes used on <li> elements (common item containers)
    li_tags = soup.find_all("li")
    classes = set()
    for li in li_tags:
        if li.get("class"):
            classes.update(li["class"])
    if classes:
        print("CSS classes found on <li> elements:")
        for c in sorted(classes):
            print(f"  - {c}")
    else:
        print("No <li> elements with classes found.")

    # Also check for any elements that might contain product data
    # Look for common eBay selectors even if not in <li>
    possible_items = soup.select("[class*='s-item'], [class*='item']")
    print(f"Elements with class containing 's-item' or 'item': {len(possible_items)}")

except Exception as e:
    print(f"Error: {e}")

# Write an empty CSV so the detector doesn't crash (placeholder)
with open(TODAY_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "price", "link"])
    writer.writeheader()

print("Deep inspection complete. Check the log for details.")
