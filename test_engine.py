import time
import random
import re
from playwright.sync_api import sync_playwright

CATEGORIES = [
    ("laptops", "https://www.ebay.com/sch/i.html?_nkw=laptop&_sop=15&rt=nc&LH_BIN=1"),
]

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
            print(f"  Timeout: {e}")
            continue

        page.mouse.wheel(0, 1500)
        time.sleep(2)

        item_links = page.locator("a[href*='/itm/']").all()
        print(f"  Found {len(item_links)} item links. Examining first 3...\n")

        for idx, link_element in enumerate(item_links[:3]):
            try:
                raw_link = link_element.get_attribute("href")
                print(f"--- Link {idx+1}: {raw_link[:100]}... ---")

                # Walk up to find a container with both a price and a meaningful text
                container = link_element
                for depth in range(10):
                    if container is None:
                        break
                    html_snippet = container.evaluate("node => node.outerHTML")
                    # Check for price pattern
                    price_match = re.search(r'\$\d{1,3}(?:,\d{3})*(?:\.\d{2})?', html_snippet)
                    # Collect all text pieces
                    text_elements = container.query_selector_all("span, h3, div, a")
                    texts = [el.text_content().strip() for el in text_elements if el.text_content().strip()]
                    long_texts = [t for t in texts if len(t) > 10 and not t.startswith("$")]
                    if price_match and long_texts:
                        print(f"  Found container at depth {depth}:")
                        print(f"    Price found: {price_match.group()}")
                        print(f"    Longest text: '{max(long_texts, key=len)}' (len {len(max(long_texts, key=len))})")
                        print(f"    Container HTML (first 500 chars): {html_snippet[:500]}...")
                        print()
                        break
                    container = container.evaluate("node => node.parentElement")
                else:
                    print("  Could not find a container with both price and long text.\n")
            except Exception as e:
                print(f"  Error inspecting link: {e}\n")

    browser.close()
