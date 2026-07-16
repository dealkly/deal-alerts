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

# List of eBay search URLs for different categories
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
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
# --------------------------------------------

# Step 1: Rotate the CSV files (same as before)
if os.path.exists(TODAY_CSV):
    if os.path.exists(YESTERDAY_CSV):
        os.remove(YESTERDAY_CSV)
    os.rename(TODAY_CSV, YESTERDAY_CSV)

# Step 2: Scrape all categories
all_items = []
total_products = 0

for category, url in SEARCH_URLS:
    print(f"Scraping category: {category}")
    try:
        response = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(response.text, "html.parser")

        listings = soup.select("li.s-item")
        for item in listings:
            title_elem = item.select_one(".s-item__title span")
            price_elem = item.select_one(".s-item__price")
            link_elem = item.select_one(".s-item__link")

            if title_elem and price_elem and link_elem:
                title = title_elem.text.strip()
                price_text = price_elem.text.strip()
                link = link_elem.get("href")

                # Clean price: extract number
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
                total_products += 1

        time.sleep(random.uniform(2, 4))  # polite delay between categories

    except Exception as e:
        print(f"  Error scraping {category}: {e}")
        continue

# Save to CSV (same filename as before so price_detector works)
with open(TODAY_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "price"])
    writer.writeheader()
    for item in all_items:
        writer.writerow({"title": item["title"], "price": item["price"]})

print(f"\nDone. {total_products} products saved to {TODAY_CSV}")
