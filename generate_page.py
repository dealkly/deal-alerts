import pandas as pd
import os
import re

YESTERDAY_CSV = "books_yesterday.csv"
TODAY_CSV = "books_today.csv"
DEALS_HTML = "deals.html"

MIN_DROP_PERCENT = 10.0
MIN_ITEM_PRICE = 5.00

FEATURED_START = "<!-- DYNAMIC_FEATURED_START -->"
FEATURED_END = "<!-- DYNAMIC_FEATURED_END -->"
DEALS_START = "<!-- DYNAMIC_DEALS_START -->"
DEALS_END = "<!-- DYNAMIC_DEALS_END -->"


def clean_price(price_str):
    clean_str = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(clean_str)
    except ValueError:
        return None


def detect_price_drops():
    if not os.path.exists(YESTERDAY_CSV) or not os.path.exists(TODAY_CSV):
        print("Missing CSV files. Deals page not generated.")
        return pd.DataFrame()

    yest = pd.read_csv(YESTERDAY_CSV)
    today = pd.read_csv(TODAY_CSV)

    yest["price"] = yest["price"].apply(clean_price)
    today["price"] = today["price"].apply(clean_price)

    yest = yest.dropna(subset=["price"])
    today = today.dropna(subset=["price"])

    yest = yest.drop_duplicates(subset=["title"], keep="first")
    today = today.drop_duplicates(subset=["title"], keep="first")

    merged = pd.merge(yest, today, on="title", suffixes=("_yest", "_today"))
    merged["drop"] = merged["price_today"] - merged["price_yest"]

    drops = merged[merged["drop"] < 0].copy()
    return drops


def get_deal_url(row):
    for col in ["link_today", "link", "url_today", "url", "link_yest"]:
        if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
            return str(row[col]).strip()
    return ""


def get_deal_image(row):
    for col in ["image_today", "image", "image_url", "img_today", "img", "thumbnail", "image_yest"]:
        if col in row and pd.notna(row[col]):
            val = str(row[col]).strip()
            if val.lower() not in ["", "nan", "none"]:
                if ".webp" in val.lower():
                    val = re.sub(r'\.webp', '.jpg', val, flags=re.IGNORECASE)
                return val
    return ""


def build_deal_card(title, was, now, percent, link, image, badge_text, badge_bg, use_diamond):
    if image:
        img_block = (
            '<div class="h-48 bg-white flex items-center justify-center p-4 border-b border-gray-100">'
            f'<a href="{link}" target="_blank" rel="noopener noreferrer">'
            f'<img src="{image}" alt="Product" class="max-h-full object-contain">'
            '</a></div>'
        )
    else:
        img_block = (
            '<div class="h-48 bg-white flex items-center justify-center p-4 border-b border-gray-100">'
            '<div class="text-gray-400 text-sm">Image not available</div>'
            '</div>'
        )

    if use_diamond:
        diamond_svg = (
            '<span class="spin-icon">'
            '<svg width="12" height="12" viewBox="0 0 24 24" fill="none">'
            '<path d="M6 3H18L22 9H2L6 3Z" fill="#FFD700"/>'
            '<path d="M6 3L9 9H15L18 3H6Z" fill="#FFF3A0"/>'
            '<path d="M12 3L9 9H15L12 3Z" fill="#FFE57F"/>'
            '<path d="M2 9L12 21L22 9H2Z" fill="#DAA520"/>'
            '<path d="M9 9L12 21L15 9H9Z" fill="#FFD700"/>'
            '<path d="M2 9L9 9L12 21L2 9Z" fill="#B8860B"/>'
            '</svg></span>'
        )
        badge_inner = f'{diamond_svg} {badge_text}'
    else:
        badge_inner = f'🏷️ {badge_text}'

    return f"""
                <div class="bg-white border border-gray-200 rounded-xl overflow-hidden shadow-sm hover:shadow-md transition flex flex-col relative">
                    <div class="absolute top-3 left-3 z-10 text-white text-[10px] font-bold px-3 py-1.5 rounded uppercase tracking-wider flex items-center gap-1 shadow-sm" style="background-color:{badge_bg};">
                        {badge_inner}
                    </div>
                    {img_block}
                    <div class="p-5 flex flex-col flex-grow">
                        <h2 class="text-sm font-bold text-gray-900 leading-snug mb-3 line-clamp-2">{title}</h2>
                        <div class="mt-auto">
                            <div class="flex items-end justify-between mb-4">
                                <div>
                                    <p class="text-xs text-gray-500 font-semibold uppercase tracking-wider mb-0.5">Was <span class="line-through">${was:.2f}</span></p>
                                    <p class="text-2xl font-extrabold text-gray-900 leading-none">${now:.2f}</p>
                                </div>
                                <div class="bg-green-100 text-green-800 text-sm font-bold px-2 py-1 rounded">Save {percent}%</div>
                            </div>
                            <a href="{link}" target="_blank" rel="noopener noreferrer" class="block w-full text-center text-white font-bold py-3 rounded-lg transition" style="background: linear-gradient(135deg, #D97706, #B45309);">VIEW DEAL ON EBAY →</a>
                        </div>
                    </div>
                </div>
"""


def build_featured_banner(top_deal):
    if not top_deal:
        return """<div class="bg-white border border-amber-200 rounded-xl p-5 shadow-sm">
                    <p class="text-xs font-bold uppercase tracking-wider text-amber-700 mb-1">Verified Deal Tracker</p>
                    <p class="text-sm text-gray-700">
                        Dealkly scans eBay every 4 hours and flags genuine price drops of 10% or more. Free email alerts available.
                    </p>
                </div>"""

    title, was, now, percent, link, image = top_deal
    img_html = f'<img src="{image}" alt="Product" class="w-20 h-20 object-contain rounded-lg bg-white border border-gray-200 p-1">' if image else ''
    return f"""<div class="bg-white border border-amber-300 rounded-xl p-5 shadow-sm flex flex-col sm:flex-row items-center gap-5">
                    {img_html}
                    <div class="flex-grow">
                        <p class="text-xs font-bold uppercase tracking-wider text-amber-700 mb-1">Top Deal Today</p>
                        <a href="{link}" target="_blank" rel="noopener noreferrer" class="text-sm font-bold text-gray-900 hover:text-amber-700 transition leading-snug">{title}</a>
                        <div class="flex items-center gap-3 mt-2">
                            <span class="text-lg font-extrabold text-gray-900">${now:.2f}</span>
                            <span class="text-sm text-gray-500 line-through">${was:.2f}</span>
                            <span class="bg-green-100 text-green-800 text-xs font-bold px-2 py-0.5 rounded">Save {percent}%</span>
                        </div>
                    </div>
                    <a href="{link}" target="_blank" rel="noopener noreferrer" class="flex-shrink-0 text-white font-bold py-2 px-5 rounded-lg transition text-sm" style="background: linear-gradient(135deg, #D97706, #B45309);">VIEW DEAL →</a>
                </div>"""


def build_deals_grid(drops):
    if drops.empty:
        return """<div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="deal-grid">
                    <div class="bg-white border border-gray-200 rounded-xl p-6 text-center text-gray-500 md:col-span-2">
                        No qualifying deals right now. Check back after the next scheduled scan.
                    </div>
                </div>"""

    filtered = drops[
        ((-drops["drop"] / drops["price_yest"]) * 100 >= MIN_DROP_PERCENT)
        & (drops["price_today"] >= MIN_ITEM_PRICE)
    ].copy()

    if filtered.empty:
        return """<div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="deal-grid">
                    <div class="bg-white border border-gray-200 rounded-xl p-6 text-center text-gray-500 md:col-span-2">
                        No qualifying deals right now. Check back after the next scheduled scan.
                    </div>
                </div>"""

    cards = []
    top_deal = None
    best_percent = -1

    for _, row in filtered.iterrows():
        url = get_deal_url(row)
        if not url:
            continue

        percent = round((-row["drop"] / row["price_yest"]) * 100)
        save = float(-row["drop"])
        image = get_deal_image(row)

        if percent > best_percent:
            best_percent = percent
            top_deal = (
                str(row["title"]).strip(),
                float(row["price_yest"]),
                float(row["price_today"]),
                percent,
                url,
                image,
            )

        if percent >= 25 or save >= 100:
            badge_text, badge_bg, use_diamond = "WHALE DEAL", "#FF7F50", True
        elif percent >= 15 or save >= 50:
            badge_text, badge_bg, use_diamond = "MEGA DROP", "#DC2626", True
        else:
            badge_text, badge_bg, use_diamond = "PRICE DROP", "#0B1D3A", False

        card = build_deal_card(
            str(row["title"]).strip(),
            float(row["price_yest"]),
            float(row["price_today"]),
            percent,
            url,
            image,
            badge_text,
            badge_bg,
            use_diamond,
        )
        cards.append(card)

    if not cards:
        return """<div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="deal-grid">
                    <div class="bg-white border border-gray-200 rounded-xl p-6 text-center text-gray-500 md:col-span-2">
                        No qualifying deals right now. Check back after the next scheduled scan.
                    </div>
                </div>"""

    inner = "\n".join(cards)
    grid = f"""<div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="deal-grid">
{inner}
                </div>"""
    return grid, top_deal


def update_marker(content, start, end, replacement):
    pattern = re.compile(re.escape(start) + r".*?" + re.escape(end), re.DOTALL)
    return pattern.sub(f"{start}\n{replacement}\n{end}", content)


def main():
    drops = detect_price_drops()

    if drops is None or drops.empty:
        deals_grid = """<div class="grid grid-cols-1 md:grid-cols-2 gap-6" id="deal-grid">
                    <div class="bg-white border border-gray-200 rounded-xl p-6 text-center text-gray-500 md:col-span-2">
                        No qualifying deals right now. Check back after the next scheduled scan.
                    </div>
                </div>"""
        featured = build_featured_banner(None)
    else:
        result = build_deals_grid(drops)
        if isinstance(result, tuple):
            deals_grid, top_deal = result
        else:
            deals_grid = result
            top_deal = None
        featured = build_featured_banner(top_deal)

    if not os.path.exists(DEALS_HTML):
        print(f"{DEALS_HTML} not found. Skipping.")
        return

    with open(DEALS_HTML, "r", encoding="utf-8") as f:
        content = f.read()

    content = update_marker(content, FEATURED_START, FEATURED_END, featured)
    content = update_marker(content, DEALS_START, DEALS_END, deals_grid)

    with open(DEALS_HTML, "w", encoding="utf-8") as f:
        f.write(content)

    print("deals.html updated with live deals.")


if __name__ == "__main__":
    main()
