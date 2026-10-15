import pandas as pd
import time
import random
import re
import os
import json
import urllib.parse
from playwright.sync_api import sync_playwright

# ------------------ CONFIG ------------------
TODAY_CSV = "books_today.csv"
YESTERDAY_CSV = "books_yesterday.csv"
WATCHLIST_FILE = "watchlist.json"

CATEGORIES = [
    # High‑resale Tech & Hardware
    ("MacBook Pro", "https://www.ebay.com/sch/i.html?_nkw=macbook+pro+m1&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Sony WH-1000XM5", "https://www.ebay.com/sch/i.html?_nkw=sony+wh-1000xm5&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("PlayStation 5", "https://www.ebay.com/sch/i.html?_nkw=playstation+5+console&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("AirPods Pro", "https://www.ebay.com/sch/i.html?_nkw=airpods+pro+2nd+gen&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Nintendo Switch", "https://www.ebay.com/sch/i.html?_nkw=nintendo+switch+oled&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Samsung Galaxy S24", "https://www.ebay.com/sch/i.html?_nkw=samsung+galaxy+s24+ultra&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Dell XPS 13", "https://www.ebay.com/sch/i.html?_nkw=dell+xps+13+2023&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Graphic Cards", "https://www.ebay.com/sch/i.html?_nkw=rtx+4080&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),

    # High‑margin fashion & collectibles
    ("Jordan 1 Retro", "https://www.ebay.com/sch/i.html?_nkw=jordan+1+retro+high&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Designer Handbags", "https://www.ebay.com/sch/i.html?_nkw=designer+handbag&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Rare LEGO Sets", "https://www.ebay.com/sch/i.html?_nkw=lego+set+rare&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Vintage Video Games", "https://www.ebay.com/sch/i.html?_nkw=vintage+video+game+lot&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),

    # Tools, drones, wearables & smart home
    ("Drones", "https://www.ebay.com/sch/i.html?_nkw=dji+drone&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("High‑End Power Tools", "https://www.ebay.com/sch/i.html?_nkw=dewalt+tool+kit&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Fitness Trackers", "https://www.ebay.com/sch/i.html?_nkw=fitness+tracker+garmin&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
    ("Smart Home Hubs", "https://www.ebay.com/sch/i.html?_nkw=smart+home+hub&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"),
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


def load_premium_keywords():
    """Read watchlist.json and return a sorted list of unique keywords."""
    if not os.path.exists(WATCHLIST_FILE):
        return []

    try:
        with open(WATCHLIST_FILE, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Could not read watchlist.json: {e}")
        return []

    if not isinstance(data, list):
        return []

    seen = set()
    for entry in data:
        if not isinstance(entry, dict):
            continue
        for kw in entry.get("keywords", []):
            if isinstance(kw, str):
                clean = kw.strip().lower()
                if clean:
                    seen.add(clean)
    return sorted(seen)


def build_premium_search_url(keyword):
    """Convert a keyword into an eBay search URL, matching the free-search filters."""
    encoded = urllib.parse.quote_plus(keyword)
    return (
        f"https://www.ebay.com/sch/i.html?_nkw={encoded}"
        f"&_sacat=0&LH_ItemCondition=1000&_sop=15&rt=nc&LH_BIN=1"
    )


# Rotate CSV files
if os.path.exists(TODAY_CSV):
    if os.path.exists(YESTERDAY_CSV):
        os.remove(YESTERDAY_CSV)
    os.rename(TODAY_CSV, YESTERDAY_CSV)

premium_keywords = load_premium_keywords()
premium_searches = [(kw, build_premium_search_url(kw)) for kw in premium_keywords]

print(f"Premium keywords loaded: {len(premium_keywords)}")
for kw, _ in premium_searches:
    print(f"  + {kw}")

all_products = []

with sync_playwright() as p:
    browser = p.chromium.launch(
        headless=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage"
        ]
    )
    context = browser.new_context(
        viewport={"width": 1920, "height": 1080},
        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    )
    page = context.new_page()

    print("Warming up session on eBay homepage...")
    page.goto("https://www.ebay.com", wait_until="domcontentloaded")
    time.sleep(random.uniform(2, 4))

    # Build the full search list: 16 free + all premium keywords
    search_plan = [(cat, url, "free", cat) for cat, url in CATEGORIES]
    search_plan += [(kw, url, "premium", kw) for kw, url in premium_searches]

    for label, url, source, keyword in search_plan:
        print(f"Scraping [{source}] {label}")
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            print(f"  Page title seen: {page.title()}")

            if "Pardon Our Interruption" in page.title():
                print(f"  Blocked by eBay. Skipping {label}.")
                continue

            page.wait_for_selector("a[href*='/itm/']", timeout=20000)
        except Exception as e:
            print(f"  Timeout/error loading {label}: {e}")
            print("  Re‑warming session...")
            try:
                page.goto("https://www.ebay.com", wait_until="domcontentloaded")
                time.sleep(random.uniform(2, 4))
            except Exception:
                pass
            continue

        # Gradual scroll to load all items
        for _ in range(4):
            page.mouse.wheel(0, 2000)
            time.sleep(random.uniform(1.5, 2.5))
            page.mouse.move(random.randint(100, 800), random.randint(100, 600))

        # Extraction (same logic as before)
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

                    let itemPrice = null;
                    const priceRegex = /(?:US\\s*\\$|\\$|£|€)\\s?[0-9]{1,3}(?:,?[0-9]{3})*(?:\\.[0-9]{2})?/;
                    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
                    let node;
                    while ((node = walker.nextNode())) {
                        const text = node.nodeValue.trim();
                        const match = text.match(priceRegex);
                        if (match) { itemPrice = match[0]; break; }
                    }

                    let shippingText = null;
                    const shippingEl = container.querySelector('.s-item__shipping, .s-item__shipping-cost, .s-item__shipping-price, [class*="shipping"]');
                    if (shippingEl) {
                        shippingText = shippingEl.textContent.trim();
                    } else {
                        const allText = container.innerText;
                        const shipMatch = allText.match(/(\\+?\\$\\d{1,3}(?:,\\d{3})*(?:\\.\\d{2})?\\s*shipping)|(Free\\s*shipping)/i);
                        if (shipMatch) shippingText = shipMatch[0];
                    }

                    let totalPrice = itemPrice;
                    if (shippingText && !/free/i.test(shippingText)) {
                        const shipPriceMatch = shippingText.match(/\\$[\\d,]+\\.?\\d*/);
                        if (shipPriceMatch) {
                            const shipVal = parseFloat(shipPriceMatch[0].replace('$','').replace(',',''));
                            if (!isNaN(shipVal)) {
                                const itemVal = parseFloat(itemPrice.replace('$','').replace(',',''));
                                if (!isNaN(itemVal)) {
                                    totalPrice = '$' + (itemVal + shipVal).toFixed(2);
                                }
                            }
                        }
                    }

                    let condition = null;
                    const condSelectors = ['.s-item__subtitle', '.SECONDARY_INFO', '[class*="condition"]', '[class*="subtitle"]'];
                    for (const sel of condSelectors) {
                        const el = container.querySelector(sel);
                        if (el) { condition = el.textContent.trim(); break; }
                    }
                    if (!condition) {
                        const ct = container.innerText;
                        const matches = ct.match(/(Brand New|New\\s*\\(Other\\)|Open box|Certified Refurbished|Seller Refurbished|Used|Pre-owned|For parts or not working)/i);
                        if (matches) condition = matches[0];
                    }

                    const img = container.querySelector('img');
                    const imgSrc = img ? (img.getAttribute('src') || img.getAttribute('data-src') || '') : '';
                    const hasImage = imgSrc && !imgSrc.includes('placeholder') && !imgSrc.includes('no-image');
                    const containerText = container.innerText.toLowerCase();
                    const isOutOfStock = containerText.includes('out of stock') || containerText.includes('sold out');

                    if (title && itemPrice && !isOutOfStock) {
                        seenUrls.add(url);
                        results.push({
                            title: title,
                            price: itemPrice,
                            shipping: shippingText || 'Not specified',
                            total_price: totalPrice,
                            url: url,
                            condition: condition || 'Unknown',
                            hasImage: hasImage,
                            image: imgSrc
                        });
                    }
                });
                return results;
            }
        """)

        # Filter new & available items
        category_items = 0
        for item in products:
            condition = item.get("condition", "").lower()
            is_new = any(word in condition for word in ["brand new", "new", "unused"])
            if not is_new:
                continue
            if not item.get("hasImage", False):
                continue

            price_str = item.get("total_price") or item.get("price")
            price_num = clean_price(price_str)
            if price_num is None:
                continue

            all_products.append({
                "title": item["title"],
                "price": price_num,
                "link": item["url"],
                "category": label,
                "image": item.get("image", ""),
                "source": source,
                "keyword": keyword
            })
            category_items += 1

        print(f"  Extracted {len(products)} raw, filtered to {category_items} new & available products")
        time.sleep(random.uniform(3, 6))

    browser.close()

# Save CSV (now includes source and keyword columns)
if all_products:
    df = pd.DataFrame(all_products)
    df = df.drop_duplicates(subset=["link"])
    df[["title", "price", "link", "category", "image", "source", "keyword"]].to_csv(TODAY_CSV, index=False)
    print(f"\nDone. {len(df)} unique products saved to {TODAY_CSV}")
    free_count = (df["source"] == "free").sum()
    premium_count = (df["source"] == "premium").sum()
    print(f"  free: {free_count}  premium: {premium_count}")
else:
    print("\nNo products found. Creating empty CSV.")
    pd.DataFrame(columns=["title", "price", "link", "category", "image", "source", "keyword"]).to_csv(TODAY_CSV, index=False)
