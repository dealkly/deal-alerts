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

        # -------- Gradual scroll to trigger ALL lazy-loaded items --------
        for _ in range(4):
            page.mouse.wheel(0, 2000)
            time.sleep(random.uniform(1.5, 2.5))

        # -------- Enhanced extraction: title, price, condition, and availability --------
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

                    // 1. Title
                    const heading = container.querySelector('h2, h3, h4');
                    let title = heading ? heading.innerText : link.innerText;
                    if (title) {
                        title = title.replace(/Opens in a new window or tab/gi, '')
                                     .replace(/^New Listing/i, '')
                                     .trim();
                    }

                    // 2. Price (via TreeWalker)
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

                    // 3. Condition (e.g. "Brand New", "Refurbished", "Pre-owned")
                    let condition = null;
                    const conditionSelectors = [
                        '.s-item__subtitle',
                        '.SECONDARY_INFO',
                        '[class*="condition"]',
                        '[class*="subtitle"]'
                    ];
                    for (const sel of conditionSelectors) {
                        const el = container.querySelector(sel);
                        if (el) {
                            condition = el.textContent.trim();
                            break;
                        }
                    }
                    if (!condition) {
                        // Fallback: search the whole container text for condition keywords
                        const containerText = container.innerText;
                        const matches = containerText.match(/(Brand New|New\s*\(Other\)|Open box|Certified Refurbished|Seller Refurbished|Used|Pre-owned|For parts or not working)/i);
                        if (matches) condition = matches[0];
                    }

                    // 4. Availability check: skip if the image is missing or a placeholder
                    const img = container.querySelector('img');
                    const imgSrc = img ? (img.getAttribute('src') || '') : '';
                    const hasImage = imgSrc && !imgSrc.includes('placeholder') && !imgSrc.includes('no-image');
                    
                    // Also check for out-of-stock text
                    const containerText = container.innerText.toLowerCase();
                    const isOutOfStock = containerText.includes('out of stock') || containerText.includes('sold out');

                    if (title && price && !isOutOfStock) {
                        seenUrls.add(url);
                        results.push({
                            title: title,
                            price: price,
                            url: url,
                            condition: condition || 'Unknown',
                            hasImage: hasImage
                        });
                    }
                });
                return results;
            }
        """)

        # Filter and keep only new, available items
        category_items = 0
        for item in products:
            # Keep only items clearly marked as new (you can adjust this whitelist)
            condition = item.get("condition", "").lower()
            is_new = any(word in condition for word in ["brand new", "new", "unused"])
            if not is_new:
                continue   # skip used, refurbished, etc.

            # Skip items with no image (likely placeholder / dead listing)
            if not item.get("hasImage", False):
                continue

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

        print(f"  Extracted {len(products)} raw, filtered to {category_items} new & available products")
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
