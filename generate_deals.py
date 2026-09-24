import json
import re
import urllib.request


PRODUCTS_FILE = "gumroad_products.json"
TOOLS_HTML = "tools.html"

START_MARKER = "<!-- DYNAMIC_GUMROAD_START -->"
END_MARKER = "<!-- DYNAMIC_GUMROAD_END -->"


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


def build_grid(products):
    cards = []
    for product in products:
        image_url = fetch_og_image(product["page_url"])
        print(f"Fetched image for {product['name']}: {image_url}")
        cards.append(build_card(product, image_url))

    inner = "\n".join(cards)
    return f'<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">\n{inner}\n                </div>'


def update_html(grid_block):
    with open(TOOLS_HTML, "r", encoding="utf-8") as f:
        content = f.read()

    if START_MARKER not in content or END_MARKER not in content:
        print("Markers not found in tools.html")
        return

    pattern = re.compile(
        re.escape(START_MARKER) + r".*?" + re.escape(END_MARKER),
        re.DOTALL,
    )

    replacement = f"{START_MARKER}\n                {grid_block}\n                {END_MARKER}"

    new_content = pattern.sub(replacement, content)

    with open(TOOLS_HTML, "w", encoding="utf-8") as f:
        f.write(new_content)

    print("tools.html updated with live Gumroad deals.")


def main():
    with open(PRODUCTS_FILE, "r", encoding="utf-8") as f:
        products = json.load(f)

    grid_block = build_grid(products)
    update_html(grid_block)


if __name__ == "__main__":
    main()
