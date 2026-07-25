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
    # Remove any non-numeric except dot
    clean_str = re.sub(r'[^\d.]', '', price_str)
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
            page.wait_for_selector("a[href*='/itm/']", timeout=20000)
        except Exception as e:
            print(f"  Timeout/error loading {category}: {e}")
            continue

        # Scroll all the way to the bottom to trigger all lazy-loaded items
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        time.sleep(random.uniform(2, 4))

        # -------- Robust extraction logic (No CSS Classes needed) --------
        products = page.evaluate("""
            () => {
                const results = [];
                const seenUrls = new Set();
                const links = document.querySelectorAll('a[href*="/itm/"]');

                links.forEach(link => {
                    const url = link.href.split('?')[0];
                    if (seenUrls.has(url)) return;

                    let container = link.closest('li') || link.parentElement?.parentElement?.parentElement?.parentElement;
                    if (!container) return;

                    const heading = container.querySelector('h2, h3, h4');
                    let title = heading ? heading.innerText : link.innerText;
                    if (title) {
                        title = title.replace(/Opens in a new window or tab/gi, '')
                                     .replace(/^New Listing/i, '')
                                     .trim();
                    }

                    let price = null;
                    const priceRegex = /(?:US\s*\$|\$|£|€)\s?[0-9]{1,3}(?:,?[0-9]{3})*(?:\.[0-9]{2})?/;
                    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
                    let node;
                    while ((node = walker.nextNode())) {
                        const text = node.nodeValue.trim();
                        const match = text.match(priceRegex);
                        if (match) {
                            price = match[0];
                            break;
                        }
                    }

                    if (title && price) {
                        seenUrls.add(url);
                        results.push({
                            title: title,
                            price: price,
                            url: url
                        });
                    }
                });
                return results;
            }
        """)

        # Process extracted products
        category_items = 0
        for item in products:
            price_num = clean_price(item["price"])
            if price_num is None:
                continue
            all_products.append({
                "title": item["title"],
                "price": price_num,
                "link": item["url"],
                "category": category
            })
            category_items += 1

        print(f"  Extracted {category_items} products")
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
