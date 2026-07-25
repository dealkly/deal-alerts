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

# Step 3: Scrape each category using JSON‑LD first, then fallback to CSS
for category, url in SEARCH_URLS:
    print(f"Scraping category: {category}")
    try:
        response = session.get(url, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        # ---------- METHOD 1: Extract from JSON-LD (more stable) ----------
        items_found = 0
        json_ld_script = soup.find("script", type="application/ld+json")
        if json_ld_script:
            try:
                data = json.loads(json_ld_script.string)
                # The JSON-LD may contain an ItemList with products
                if isinstance(data, dict) and data.get("@type") == "ItemList":
                    for element in data.get("itemListElement", []):
                        item = element.get("item", element)
                        name = item.get("name")
                        # Price may be stored as a number or string
                        price_raw = item.get("offers", {}).get("price")
                        product_url = item.get("url") or item.get("@id")
                        if name and price_raw is not None:
                            try:
                                price = float(price_raw)
                            except:
                                continue
                            all_items.append({
                                "title": name.strip(),
                                "price": price,
                                "link": product_url,
                                "category": category
                            })
                            items_found += 1
                elif isinstance(data, list):
                    # Sometimes the JSON is an array of items directly
                    for item in data:
                        if item.get("@type") == "Product":
                            name = item.get("name")
                            price_raw = item.get("offers", {}).get("price")
                            product_url = item.get("url") or item.get("@id")
                            if name and price_raw is not None:
                                try:
                                    price = float(price_raw)
                                except:
                                    continue
                                all_items.append({
                                    "title": name.strip(),
                                    "price": price,
                                    "link": product_url,
                                    "category": category
                                })
                                items_found += 1
            except (json.JSONDecodeError, KeyError, TypeError):
                pass

        print(f"  JSON-LD method found: {items_found} items")

        # ---------- METHOD 2: Fallback to HTML parsing ----------
        if items_found == 0:
            listings = soup.select("li.s-item")
            html_count = 0
            for item in listings:
                title_elem = item.select_one(".s-item__title span")
                price_elem = item.select_one(".s-item__price")
                link_elem = item.select_one(".s-item__link")
                if title_elem and price_elem and link_elem:
                    title = title_elem.text.strip()
                    price_text = price_elem.text.strip()
                    link = link_elem.get("href")
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
                    html_count += 1
            print(f"  HTML fallback found: {html_count} items")
            items_found = html_count

        total_products += items_found

        time.sleep(random.uniform(2, 4))

    except Exception as e:
        print(f"  Error scraping {category}: {e}")
        continue

# Step 4: Save to CSV
with open(TODAY_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "price", "link"])
    writer.writeheader()
    for item in all_items:
        writer.writerow({"title": item["title"], "price": item["price"], "link": item["link"]})

print(f"\nDone. {total_products} products saved to {TODAY_CSV}")
