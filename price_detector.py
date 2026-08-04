import pandas as pd
import time
import random
import re
import os
from playwright.sync_api import sync_playwright

# ------------------ CONFIG ------------------
TODAY_CSV = "books_today.csv"
YESTERDAY_CSV = "books_yesterday.csv"

CATEGORIES = [
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

def clean_price(price_str):
    first_price = price_str.split("to")[0].split("-")[0]
    clean_str = re.sub(r'[^\d.]', '', first_price)
    try:
        return float(clean_str)
    except ValueError:
        return None

def clean_link(url):
    if "?" in url:
        return url.split("?")[0]
    return url

# Rotate CSV files
if os.path.exists(TODAY_CSV):
    if os.path.exists(YESTERDAY_CSV):
        os.remove(YESTERDAY_CSV)
    os.rename(TODAY_CSV, YESTERDAY_CSV)

all_items = []
total_products = 0

# Warm up session
session = requests.Session()
session.headers.update(HEADERS)

print("Warming up session (eBay homepage)...")
try:
    session.get("https://www.ebay.com", timeout=15)
    time.sleep(random.uniform(1, 2))
except Exception as e:
    print(f"Warm‑up error (continuing): {e}")

# Scrape each category
with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    for category, url in CATEGORIES:
        print(f"Scraping category: {category}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            # Scroll to load all items
            for _ in range(4):
                page.mouse.wheel(0, 2000)
                time.sleep(random.uniform(1.5, 2.5))

            # Extract product cards using the /itm/ link method
            items = page.locator("a[href*='/itm/']").all()
            print(f"  Found {len(items)} raw elements")

            seen_urls = set()
            for link_element in items:
                try:
                    raw_link = link_element.get_attribute("href", timeout=500)
                    if not raw_link or '/itm/' not in raw_link:
                        continue
                    clean_url = clean_link(raw_link)
                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)

                    # Walk up the DOM to find the container card
                    container = link_element
                    title = None
                    price = None
                    image_url = None
                    for _ in range(10):
                        if container is None:
                            break
                        # Try to get title
                        title_el = container.query_selector(".s-item__title")
                        if title_el:
                            title = title_el.inner_text().strip()
                        # Try to get price
                        price_el = container.query_selector(".s-item__price")
                        if price_el:
                            price_text = price_el.inner_text().strip()
                            price = clean_price(price_text)
                        # Try to get image
                        img_el = container.query_selector("img")
                        if img_el:
                            image_url = img_el.get_attribute("src") or img_el.get_attribute("data-src")
                        if title and price is not None:
                            break
                        container = container.evaluate("node => node.parentElement")

                    if title and price is not None:
                        all_items.append({
                            "title": title,
                            "price": price,
                            "link": clean_url,
                            "image": image_url if image_url else "",
                            "category": category
                        })
                        total_products += 1
                except Exception:
                    continue

        except Exception as e:
            print(f"  Error scraping {category}: {e}")
            continue

    browser.close()

# Save CSV (now includes image column)
with open(TODAY_CSV, "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["title", "price", "link", "image"])
    writer.writeheader()
    for item in all_items:
        writer.writerow({
            "title": item["title"],
            "price": item["price"],
            "link": item["link"],
            "image": item.get("image", "")
        })

print(f"\nDone. {total_products} products saved to {TODAY_CSV}")
