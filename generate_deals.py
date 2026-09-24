import json
import re
import urllib.request


PRODUCTS_FILE = "gumroad_products.json"
DEALS_HTML = "deals.html"
TOOLS_HTML = "tools.html"

GUMROAD_START = "<!-- DYNAMIC_GUMROAD_START -->"
GUMROAD_END = "<!-- DYNAMIC_GUMROAD_END -->"
SIDEBAR_START = "<!-- DYNAMIC_SIDEBAR_START -->"
SIDEBAR_END = "<!-- DYNAMIC_SIDEBAR_END -->"


def fetch_og_image(url):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=15) as response:
            html = response.read().decode("utf-8", errors="ignore")

        match = re.search(
            r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
                html,
                re.IGNORECASE,
            )
        if match:
            return match.group(1)
    except Exception as e:
        print(f"Warning: could not fetch image for {url}: {e}")

    return ""


def build_card(product, image_url):
    if image_url:
        image_html = (
            f'<div class="h-40 bg-white flex items-center justify-center p-4 border-b border-gray-100">'
            f'<a href="{product["affiliate_url"]}" target="_blank" rel="noopener noreferrer">'
            f'<img src="{image_url}" alt="{product["name"]}" class="max-h-full object-contain">'
            f'</a></div>'
        )
    else:
        image_html = (
            f'<div class="h-40 flex items-center justify-center p-4 border-b border-gray-100" '
            f'style="background-color:{product["bg_color"]};">'
            f'<span class="text-2xl font-extrabold" style="color:{product["label_color"]};">'
            f'{product["label"]}</span></div>'
        )

    return f"""
                    <div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition flex flex-col relative">
                        <div class="absolute top-3 left-3 z-10 text-white text-[10px] font-bold px-3 py-1.5 rounded uppercase tracking-wider shadow-sm" style="background-color:{product["badge_color"]};">
                            {product["badge"]}
                        </div>
                        {image_html}
                        <div class="p-5 flex flex-col flex-grow">
                            <h2 class="text-sm font-bold text-gray-900 leading-snug mb-3 line-clamp-2">{product["name"]}</h2>
                            <p class="text-xs text-gray-500 mb-4">{product["description"]}</p>
                            <div class="mt-auto">
                                <a href="{product["affiliate_url"]}" target="_blank" rel="noopener noreferrer" class="block w-full text-center text-white font-bold py-3 rounded-lg transition" style="background: linear-gradient(135deg, #D97706, #B45309);">VIEW ON GUMROAD →</a>
                            </div>
                        </div>
                    </div>
"""


def build_sidebar_item(product, image_url):
    if image_url:
        icon_html = (
            f'<div class="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0 bg-white border border-gray-200 p-1">'
            f'<img src="{image_url}" alt="{product["name"]}" class="max-w-full max-h-full object-contain">'
            f'</div>'
        )
    else:
        icon_html = (
            f'<div class="w-12 h-12 rounded-lg flex items-center justify-center flex-shrink-0" '
            f'style="background:linear-gradient(135deg,{product["label_color"]},{product["badge_color"]});">'
            f'<span class="text-white text-[9px] font-bold text-center leading-tight px-1">{product["label"]}</span>'
            f'</div>'
        )

    return f"""
                        <a href="{product["affiliate_url"]}" target="_blank" rel="noopener noreferrer" class="flex items-start gap-3 group">
                            {icon_html}
                            <div class="flex-grow">
                                <p class="text-xs font-bold text-gray-900 group-hover:text-amber-700 transition leading-snug">{product["name"]}</p>
                                <p class="text-[11px] text-gray-500 mt-1">{product["description"]}</p>
                            </div>
                        </a>
"""


def build_grid(products, images):
    cards = []
    for product in products:
        image_url = images.get(product["page_url"], "")
        cards.append(build_card(product, image_url))

    inner = "\n".join(cards)
    return f'<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">\n{inner}\n                </div>'


def build_sidebar(products, images):
    items = []
    for product in products[:3]:
        image_url = images.get(product["page_url"], "")
        items.append(build_sidebar_item(product, image_url))

    return "\n".join(items)


def update_marker(content, start, end, replacement):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    return pattern.sub(f"{start}\n{replacement}\n{end}", content)


def main():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        products = json.load(f)

    # Fetch each product image once
    images = {}
    for product in products:
        url = product["page_url"]
        img = fetch_og_image(url)
        images[url] = img
        print(f"Fetched image for {product['name']}: {img}")

    grid_block = build_grid(products, images)
    sidebar_block = build_sidebar(products, images)

    # Update tools.html with full grid
    with open(TOOLS_HTML, "r", encoding="utf-8") as f:
        tools_content = f.read()

    if GUMROAD_START in tools_content and GUMROAD_END in tools_content:
        tools_content = update_marker(tools_content, GUMROAD_START, GUMROAD_END, grid_block)
        with open(TOOLS_HTML, "w", encoding="utf-8") as f:
            f.write(tools_content)
        print("tools.html updated with live Gumroad deals.")
    else:
        print("GUMROAD markers not found in tools.html")

    # Update deals.html sidebar widget
    with open(DEALS_HTML, "r", encoding="utf-8") as f:
        deals_content = f.read()

    if SIDEBAR_START in deals_content and SIDEBAR_END in deals_content:
        deals_content = update_marker(deals_content, SIDEBAR_START, SIDEBAR_END, sidebar_block)
        with open(DEALS_HTML, "w", encoding="utf-8") as f:
            f.write(deals_content)
        print("deals.html sidebar updated with live Gumroad deals.")
    else:
        print("SIDEBAR markers not found in deals.html")


if __name__ == "__main__":
    main()
