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

        # Gradual scroll to load all items
        for _ in range(4):
            page.mouse.wheel(0, 2000)
            time.sleep(random.uniform(1.5, 2.5))

        # -------- Extraction with total price (item + shipping) --------
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

                    // Title
                    const heading = container.querySelector('h2, h3, h4');
                    let title = heading ? heading.innerText : link.innerText;
                    if (title) {
                        title = title.replace(/Opens in a new window or tab/gi, '')
                                     .replace(/^New Listing/i, '')
                                     .trim();
                    }

                    // Item price
                    let itemPrice = null;
                    const priceRegex = /(?:US\s*\$|\$|£|€)\s?[0-9]{1,3}(?:,?[0-9]{3})*(?:\.[0-9]{2})?/;
                    const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT, null, false);
                    let node;
                    while ((node = walker.nextNode())) {
                        const text = node.nodeValue.trim();
                        const match = text.match(priceRegex);
                        if (match) {
                            itemPrice = match[0];
                            break;
                        }
                    }

                    // Shipping cost
                    let shippingText = null;
                    // Look for a dedicated shipping element
                    const shippingEl = container.querySelector('.s-item__shipping, .s-item__shipping-cost, .s-item__shipping-price, [class*="shipping"]');
                    if (shippingEl) {
                        shippingText = shippingEl.textContent.trim();
                    } else {
                        // Search for text like "+$5.00 shipping" or "Free shipping"
                        const allText = container.innerText;
                        const shipMatch = allText.match(/(\+?\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?\s*shipping)|(Free\s*shipping)/i);
                        if (shipMatch) shippingText = shipMatch[0];
                    }

                    let totalPrice = itemPrice; // default to item price
                    if (shippingText && !/free/i.test(shippingText)) {
                        const shipPriceMatch = shippingText.match(/\$[\d,]+\.?\d*/);
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

                    // Condition
                    let condition = null;
                    const condSelectors = ['.s-item__subtitle', '.SECONDARY_INFO', '[class*="condition"]', '[class*="subtitle"]'];
                    for (const sel of condSelectors) {
                        const el = container.querySelector(sel);
                        if (el) { condition = el.textContent.trim(); break; }
                    }
                    if (!condition) {
                        const ct = container.innerText;
                        const matches = ct.match(/(Brand New|New\s*\(Other\)|Open box|Certified Refurbished|Seller Refurbished|Used|Pre-owned|For parts or not working)/i);
                        if (matches) condition = matches[0];
                    }

                    // Image check
                    const img = container.querySelector('img');
                    const imgSrc = img ? (img.getAttribute('src') || '') : '';
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
                            hasImage: hasImage
                        });
                    }
                });
                return results;
            }
        """)

        # Filter new & available items, save total_price as the tracked price
        category_items = 0
        for item in products:
            condition = item.get("condition", "").lower()
            is_new = any(word in condition for word in ["brand new", "new", "unused"])
            if not is_new: continue
            if not item.get("hasImage", False): continue

            # Use total_price if available, else fallback to item price
            price_str = item.get("total_price") or item.get("price")
            price_num = clean_price(price_str)
            if price_num is None: continue

            all_products.append({
                "title": item["title"],
                "price": price_num,          # now total estimated price (item+shipping)
                "link": item["url"],
                "category": category
            })
            category_items += 1

        print(f"  Extracted {len(products)} raw, filtered to {category_items} new & available products")
        time.sleep(random.uniform(3, 6))

    browser.close()

# Save CSV with 'price' column now representing total estimated price
if all_products:
    df = pd.DataFrame(all_products)
    df = df.drop_duplicates(subset=["link"])
    df[["title", "price", "link"]].to_csv(TODAY_CSV, index=False)
    print(f"\nDone. {len(df)} unique products saved to {TODAY_CSV}")
else:
    print("\nNo products found. Creating empty CSV.")
    pd.DataFrame(columns=["title", "price", "link"]).to_csv(TODAY_CSV, index=False)
