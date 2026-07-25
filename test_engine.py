import requests
from bs4 import BeautifulSoup
import csv
import time
import random
import re
import os

# ------------------ CONFIG ------------------
TODAY_CSV = "books_today.csv"
YESTERDAY_CSV = "books_yesterday.csv"

SEARCH_URLS = [
    ("laptops", "https://www.ebay.com/sch/i.html?_nkw=laptop&_sop=15&rt=nc&LH_BIN=1"),
    ("headphones", "https://www.ebay.com/sch/i.html?_nkw=wireless+headphones&_sop=15&rt=nc&LH_BIN=1"),
    ("sneakers", "https://www.ebay.com/sch/i.html?_nkw=men+sneakers&_sop=15&rt=nc&LH_BIN=1"),
    ("tablets", "https://www.ebay.com/sch/i.html?_nkw=tablet&_sop=15&rt=nc&LH_BIN=1"),
    ("gaming", "https://www.ebay.com/sch/i.html?_nkw=video+game+console&_sop=15&rt=nc&LH_BIN=1"),
    ("baby gear", "https://www.ebay.com/sch/i.html?_nkw=baby+gear&_sop=15&rt=nc&LH_BIN=1"),
    ("home appliances", "https://www.ebay.com/sch/i.html?_nkw=home+appliance&_sop=15&rt=nc&LH_BIN=1"),
    ("textbooks", "https://www.ebay.com/sch/i.html?_nkw=textbook&_sop=15&rt=nc&LH_BIN=1"),
]

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

# Step 1: Rotate CSV files
if os.path.exists(TODAY_CSV):
    if os.path.exists(YESTERDAY_CSV):
        os.remove(YESTERDAY_CSV)
    os.rename(TODAY_CSV, YESTERDAY_CSV)

all_items = []
total_products = 0

# Step 2: Warm up session
session = requests.Session()
session.headers.update(HEADERS)

print("Warming up session (eBay homepage)...")
try:
    session.get("https://www.ebay.com", timeout=15)
    time.sleep(random.uniform(1, 2))
except Exception as e:
    print(f"Warm‑up error (continuing): {e}")

# Step 3: Scrape each category
for category, url in SEARCH_URLS:
    print(f"Scraping category: {category}")
    try:
        response = session.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        # Use the current eBay structure: product cards are div.s-item
        items = soup.select(".s-item")
        print(f"  Found {len(items)} .s-item elements")

        category_items = 0
        for item in items:
            # Title: try the standard inner span, or the .s-item__title itself
            title_elem = item.select_one(".s-item__title span") or item.select_one(".s-item__title")
            price_elem = item.select_one(".s-item__price")
            link_elem = item.select_one(".s-item__link") or item.find("a", href=True)

            if not title_elem or not price_elem:
                continue

            title = title_elem.text.strip()
            price_text = price_elem.text.strip()
            link = link_elem.get("href") if link_elem else ""

            # Skip "Shop on eBay" or sponsored items that have no real link
            if "ebay.com" not in link:
                continue

            # Extract price number
            price_match = re.search(r"[\d,]+\.?\d*", price_text)
            if not price_match:
                continue
            price = float(price_match.group().replace(",", ""))

            all_items.append({
                "title": title,
                "price": price,
                "link": link,
                "category": category
            })
            category_items += 1

        total_products += category_items

        time.sleep(random.uniform(2, 4))  # polite delay

    except Exception as e:
        print(f"  Error scraping {category}: {e}")
        continue

# Save to CSV
with open(TODAY_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "price", "link"])
    writer.writeheader()
    for item in all_items:
        writer.writerow({"title": item["title"], "price": item["price"], "link": item["link"]})

print(f"\nDone. {total_products} products saved to {TODAY_CSV}")
