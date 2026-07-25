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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    context = browser.new_context(viewport={"width": 1920, "height": 1080})
    page = context.new_page()

    print("Warming up session on eBay homepage...")
    page.goto("https://www.ebay.com", wait_until="domcontentloaded")
    time.sleep(random.uniform(2, 4))

    for category, url in CATEGORIES:
        print(f"Scraping category: {category}")
        try:
            page.goto(url, wait_until="domcontentloaded")
            print(f"  Page title seen: {page.title()}")
            # Wait for item links to be present
            page.wait_for_selector("a[href*='/itm/']", timeout=20000)
        except Exception as e:
            print(f"  Timeout/error loading {category}: {e}")
            continue

        # Scroll to trigger lazy‑loaded content
        page.mouse.wheel(0, 1500)
        time.sleep(random.uniform(2, 4))

        # Use JavaScript to extract products directly from the DOM
        products = page.evaluate("""
            () => {
                const items = [];
                // Grab all anchor tags that link to an eBay item page
                const links = document.querySelectorAll('a[href*="/itm/"]');
                const seen = new Set();
                for (const link of links) {
                    const url = link.href.split('?')[0];  // clean URL
                    if (seen.has(url)) continue;
                    seen.add(url);

                    // Walk up to find the closest containing card that has both a price and a title
                    let container = link;
                    for (let i = 0; i < 10; i++) {
                        if (!container) break;
                        // Look for a price inside this container
                        const priceEl = container.querySelector('.s-item__price');
                        const titleEl = container.querySelector('.s-item__title');
                        if (priceEl && titleEl) {
                            const priceText = priceEl.textContent.trim();
                            // Extract the first dollar amount
                            const priceMatch = priceText.match(/\\$[\\d,]+(?:\\.\\d{2})?/);
                            if (priceMatch) {
                                const title = titleEl.textContent.trim();
                                if (title && !title.includes('Shop on eBay')) {
                                    items.push({
                                        title: title,
                                        price: priceMatch[0],
                                        link: url,
                                        category: '""" + category + """'
                                    });
                                    break;
                                }
                            }
                        }
                        container = container.parentElement;
                    }
                }
                return items;
            }
        """)

        # Clean price strings to numbers
        for prod in products:
            price_num = clean_price(prod["price"])
            if price_num is not None:
                all_products.append({
                    "title": prod["title"],
                    "price": price_num,
                    "link": clean_link(prod["link"]),
                    "category": category
                })
        print(f"  Extracted {len(products)} products")

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
