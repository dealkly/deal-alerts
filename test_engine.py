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

all_products = []
total = 0

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080}
    )
    page = context.new_page()

    print("Warming up session on eBay homepage...")
    page.goto("https://www.ebay.com", wait_until="domcontentloaded")
    time.sleep(random.uniform(2, 4))

    for category, url in CATEGORIES:
        print(f"Scraping category: {category}")
        try:
            page.goto(url, wait_until="domcontentloaded")
            print(f"  Page title seen: {page.title()}")
            
            # Wait for either li.s-item or /itm/ links to appear
            page.wait_for_selector("li.s-item, a[href*='/itm/']", timeout=20000)
        except Exception as e:
            print(f"  Timeout/error loading {category}: {e}")
            continue

        # Scroll to trigger lazy-load
        page.mouse.wheel(0, 1500)
        time.sleep(random.uniform(2, 4))

        # ---------- METHOD 1: Try li.s-item (now that fingerprint is fixed) ----------
        items = page.locator("li.s-item").all()
        if items:
            print(f"  Using li.s-item method. Found {len(items)} cards.")
            for item in items:
                try:
                    title = item.locator(".s-item__title").inner_text(timeout=500)
                    if "Shop on eBay" in title:
                        continue
                    price_text = item.locator(".s-item__price").inner_text(timeout=500)
                    raw_link = item.locator(".s-item__link").get_attribute("href", timeout=500)
                    
                    price = clean_price(price_text)
                    link = clean_link(raw_link)
                    if title and price is not None and link:
                        all_products.append({
                            "title": title,
                            "price": price,
                            "link": link,
                            "category": category
                        })
                        total += 1
                except Exception:
                    continue
        else:
            # ---------- METHOD 2: Fallback to /itm/ link extraction ----------
            print("  li.s-item not found, using /itm/ link fallback.")
            item_links = page.locator("a[href*='/itm/']").all()
            print(f"  Found {len(item_links)} item links")
            seen_urls = set()
            for link_element in item_links:
                try:
                    raw_link = link_element.get_attribute("href", timeout=500)
                    if not raw_link or '/itm/' not in raw_link:
                        continue
                    clean_url = clean_link(raw_link)
                    if clean_url in seen_urls:
                        continue
                    seen_urls.add(clean_url)

                    # Find the closest container that has both a price and a meaningful title
                    container = link_element
                    title = None
                    price = None
                    for _ in range(8):
                        if container is None:
                            break
                        # Look for price in this container
                        price_match = re.search(r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', container.text_content())
                        if price_match:
                            price = clean_price(price_match.group())
                        # Look for a title: first try an h3, then the longest meaningful text
                        h3 = container.query_selector("h3")
                        if h3:
                            title = h3.text_content().strip()
                        else:
                            texts = [el.text_content().strip() for el in container.query_selector_all("span,div")]
                            for t in sorted(texts, key=len, reverse=True):
                                if t and len(t) > 15 and not t.startswith("$") and "Shop on eBay" not in t:
                                    title = t
                                    break
                        if title and price is not None:
                            break
                        container = container.evaluate("node => node.parentElement")
                    
                    if title and price is not None:
                        all_products.append({
                            "title": title,
                            "price": price,
                            "link": clean_url,
                            "category": category
                        })
                        total += 1
                except Exception:
                    continue

        time.sleep(random.uniform(3, 6))

    browser.close()

# Save CSV
if all_products:
    df = pd.DataFrame(all_products)
    df = df.drop_duplicates(subset=["link"])
    df[["title", "price", "link"]].to_csv(TODAY_CSV, index=False)
    print(f"\nDone. {len(df)} unique products saved to {TODAY_CSV}")
else:
    print("\nNo products found. Creating empty CSV.")
    pd.DataFrame(columns=["title", "price", "link"]).to_csv(TODAY_CSV, index=False)
