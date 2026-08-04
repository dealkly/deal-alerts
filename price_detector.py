import pandas as pd
import json
import smtplib
import os
import sys
import re
import urllib.request
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 1. CONFIGURATION
# ==========================================
YESTERDAY_CSV = "books_yesterday.csv"
TODAY_CSV = "books_today.csv"
SUBSCRIBERS_FILE = "paid_subscribers.json"
SENDER = "dealkly.contact@gmail.com"
SENDER_NAME = "Dealkly Alerts"
PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

if not PASSWORD:
    raise ValueError("GMAIL_APP_PASSWORD environment variable not set.")

ADMIN_PASSWORD_INPUT = os.environ.get("ADMIN_PASSWORD_INPUT", "")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
ADMIN_TEST_MODE = (ADMIN_PASSWORD_INPUT == ADMIN_SECRET) and ADMIN_SECRET != ""

MIN_DROP_PERCENT = 10.0
MIN_ITEM_PRICE = 5.00

LOGO_URL = "https://dealkly.github.io/deal-alerts/logo_white.png"
PREMIUM_LINK = "https://dealkly.gumroad.com/l/premium-alerts"
WEBSITE_LINK = "https://dealkly.github.io/deal-alerts/"

# Rotating Gold Luxury Diamond SVG
GOLD_DIAMOND_SVG = (
    '<span class="spin-icon" style="display:inline-block;vertical-align:middle;'
    'animation:spin 3s linear infinite;-webkit-animation:spin 3s linear infinite;margin-right:5px;">'
    '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg" style="display:block;">'
    '<path d="M6 3H18L22 9H2L6 3Z" fill="#FFD700"/>'
    '<path d="M6 3L9 9H15L18 3H6Z" fill="#FFF3A0"/>'
    '<path d="M12 3L9 9H15L12 3Z" fill="#FFE57F"/>'
    '<path d="M2 9L12 21L22 9H2Z" fill="#DAA520"/>'
    '<path d="M9 9L12 21L15 9H9Z" fill="#FFD700"/>'
    '<path d="M2 9L9 9L12 21L2 9Z" fill="#B8860B"/>'
    '</svg></span>'
)


def clean_price(price_str):
    clean_str = re.sub(r'[^\d.]', '', str(price_str))
    try:
        return float(clean_str)
    except ValueError:
        return None


def load_subscribers():
    with open(SUBSCRIBERS_FILE, "r") as f:
        return json.load(f)


def fetch_ebay_image_url(page_url):
    """Extracts direct image URL and forces JPEG format to bypass Gmail WebP blocks."""
    if not page_url or not isinstance(page_url, str) or not page_url.startswith("http"):
        return ""
    
    if re.search(r'\.(jpg|jpeg|png|webp)(\?.*)?$', page_url, re.IGNORECASE) or "i.ebayimg.com" in page_url:
        return re.sub(r'\.webp', '.jpg', page_url, flags=re.IGNORECASE)

    try:
        req = urllib.request.Request(
            page_url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        )
        with urllib.request.urlopen(req, timeout=4) as response:
            html = response.read().decode('utf-8', errors='ignore')
            match = re.search(r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']', html, re.IGNORECASE)
            if not match:
                match = re.search(r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']', html, re.IGNORECASE)
            if match:
                img_url = match.group(1)
                return re.sub(r'\.webp', '.jpg', img_url, flags=re.IGNORECASE)
    except Exception as e:
        print(f"Note: Could not automatically fetch image for {page_url}: {e}")
    return ""


def detect_price_drops():
    if not os.path.exists(YESTERDAY_CSV):
        print("No yesterday data found.")
        return None, 0

    yest = pd.read_csv(YESTERDAY_CSV)
    today = pd.read_csv(TODAY_CSV)

    yest["price"] = yest["price"].apply(clean_price)
    today["price"] = today["price"].apply(clean_price)
    yest = yest.dropna(subset=["price"])
    today = today.dropna(subset=["price"])

    yest = yest.drop_duplicates(subset=["title"], keep="first")
    today = today.drop_duplicates(subset=["title"], keep="first")

    product_count = len(today)
    merged = pd.merge(yest, today, on="title", suffixes=("_yest", "_today"))

    merged["drop"] = merged["price_today"] - merged["price_yest"]
    drops = merged[merged["drop"] < 0]
    return drops, product_count


def build_sample_deal_html():
    """Return a complete HTML email with a sample deal, used for admin test."""
    sample_img = "https://i.ebayimg.com/images/g/Y8AAAOSwX6dlP7mX/s-l1600.jpg"
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
body{{margin:0;padding:0;background:#F4F6F8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}}
table{{border-collapse:collapse;}}
img{{border:0;height:auto;display:block;}}
@keyframes spin {{
  from {{ transform: rotate(0deg); -webkit-transform: rotate(0deg); }}
  to {{ transform: rotate(360deg); -webkit-transform: rotate(360deg); }}
}}
@-webkit-keyframes spin {{
  from {{ -webkit-transform: rotate(0deg); }}
  to {{ -webkit-transform: rotate(360deg); }}
}}
</style>
</head>
<body style="margin:0;padding:0;background:#F4F6F8;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#F4F6F8;padding:24px 0;">
    <tr>
      <td align="center">
        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E5E7EB;box-shadow:0 4px 12px rgba(0,0,0,0.05);">
          <tr>
            <td style="background:#0B1D3A;padding:32px 24px;text-align:center;">
              <a href="{WEBSITE_LINK}" target="_blank" style="text-decoration:none;"><img src="{LOGO_URL}" alt="" height="36" style="display:block;margin:0 auto;height:36px;width:auto;"></a>
            </td>
          </tr>
          <tr>
            <td style="padding:28px 24px 16px 24px;">
              <h2 style="color:#0F172A;margin:0 0 8px;font-size:20px;font-weight:800;">Admin Test – Sample Alert</h2>
              <p style="color:#64748B;margin:0;font-size:14px;line-height:1.5;">If you see this card, your HTML email is ready to roll!</p>
            </td>
          </tr>
          <tr>
            <td style="padding:8px 24px 24px 24px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:20px;border:1px solid #E2E8F0;border-radius:10px;background:#FFFFFF;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
                <tr>
                  <td style="padding:20px;">
                    <div style="margin-bottom:12px;">
                      <span style="background:#DC2626;color:#FFFFFF;font-size:11px;font-weight:700;padding:6px 14px;border-radius:6px;text-transform:uppercase;letter-spacing:0.8px;display:inline-block;">
                        {GOLD_DIAMOND_SVG}<span style="vertical-align:middle;">MEGA DROP</span>
                      </span>
                    </div>
                    <div style="margin:12px 0 16px 0;text-align:center;"><a href="https://dealkly.github.io/deal-alerts/" target="_blank"><img src="{sample_img}" alt="" width="160" style="max-width:160px;max-height:160px;height:auto;border-radius:8px;border:1px solid #E2E8F0;margin:0 auto;display:block;"></a></div>
                    <a href="https://dealkly.github.io/deal-alerts/" target="_blank" style="color:#0F172A;text-decoration:none;font-size:15px;font-weight:700;line-height:1.4;display:block;margin-bottom:16px;">Apple MacBook Pro 13in (M1, 8GB, 256GB) - Silver</a>
                    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:18px;">
                      <tr>
                        <td style="font-size:13px;color:#EF4444;font-weight:700;">Was: <span style="text-decoration:line-through;color:#EF4444;font-weight:700;">$1,300.00</span></td>
                        <td align="right">
                          <span style="font-size:20px;font-weight:800;color:#0F172A;">$850.00</span>
                          <span style="background:#DCFCE7;color:#166534;font-size:11px;font-weight:600;padding:4px 8px;border-radius:4px;margin-left:8px;">Save 35%</span>
                        </td>
                      </tr>
                    </table>
                    <a href="{sample_img}" target="_blank" style="display:block;width:100%;background:#0B1D3A;color:#FFFFFF;text-align:center;padding:12px 0;border-radius:6px;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;text-decoration:none;">VIEW DEAL ON EBAY →</a>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding:0 24px 28px 24px;">
              <div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:20px;text-align:center;">
                <p style="margin:0 0 12px;font-size:13px;color:#475569;line-height:1.4;">Want to track a specific item? Upgrade to Premium and we'll watch it daily for you.</p>
                <a href="{PREMIUM_LINK}" target="_blank" style="display:inline-block;background:#0B1D3A;color:#FFFFFF;padding:10px 24px;border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;">Upgrade to Premium – $3/mo</a>
              </div>
            </td>
          </tr>
          <tr>
            <td style="background:#0B1D3A;padding:24px;text-align:center;border-top:1px solid #1E293B;">
              <a href="{WEBSITE_LINK}" target="_blank" style="color:#60A5FA;font-size:12px;text-decoration:underline;">Manage Preferences & Watchlists</a>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_alert(drops):
    if drops is None:
        print("No comparison data.")
        return
    if drops.empty:
        print("Zero price drops.")
        return

    filtered = drops[((-drops["drop"] / drops["price_yest"]) * 100 >= MIN_DROP_PERCENT) & (drops["price_today"] >= MIN_ITEM_PRICE)]
    if filtered.empty:
        print("No drops passed quality filters.")
        return

    best_deal = {}
    for _, row in filtered.iterrows():
        url = ""
        for col in ["link_today", "link", "url_today", "url", "link_yest"]:
            if col in row and pd.notna(row[col]) and str(row[col]).strip() != "":
                url = str(row[col]).strip()
                break
                
        if not url:
            continue

        drop_val = -row["drop"] if row["drop"] < 0 else row["drop"]
        percent = round((drop_val / row["price_yest"]) * 100)
        
        raw_image_url = ""
        for col in ["image_today", "image", "image_url", "img_today", "img", "thumbnail", "image_yest"]:
            if col in row and pd.notna(row[col]):
                val = str(row[col]).strip()
                if val.lower() not in ["", "nan", "none"]:
                    raw_image_url = val
                    break

        clean_img = fetch_ebay_image_url(raw_image_url)
        if not clean_img and url:
            clean_img = fetch_ebay_image_url(url)

        if clean_img and ".webp" in clean_img.lower():
            clean_img = re.sub(r'\.webp', '.jpg', clean_img, flags=re.IGNORECASE)

        if url not in best_deal or percent > best_deal[url]["percent"]:
            best_deal[url] = {
                "title": str(row["title"]).strip(),
                "was": float(row["price_yest"]),
                "now": float(row["price_today"]),
                "save": float(drop_val),
                "percent": int(percent),
                "link": url,
                "image": clean_img
            }

    if not best_deal:
        print("No valid deals after parsing.")
        return

    deal_list = sorted(best_deal.values(), key=lambda x: x["percent"], reverse=True)
    
    subject = "💎 Dealkly Alert: Verified Price Drops Detected"
    text_body = "DEALKLY ALERTS - VERIFIED PRICE DROPS DETECTED\n" + "=" * 45 + "\n\nItems on your tracked list have dropped:\n\n"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Dealkly Alert</title>
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
body{{margin:0;padding:0;background:#F4F6F8;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;}}
table{{border-collapse:collapse;}}
img{{border:0;height:auto;display:block;}}
@keyframes spin {{
  from {{ transform: rotate(0deg); -webkit-transform: rotate(0deg); }}
  to {{ transform: rotate(360deg); -webkit-transform: rotate(360deg); }}
}}
@-webkit-keyframes spin {{
  from {{ -webkit-transform: rotate(0deg); }}
  to {{ -webkit-transform: rotate(360deg); }}
}}
</style>
</head>
<body style="margin:0;padding:0;background:#F4F6F8;">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background:#F4F6F8;padding:24px 0;"><tr><td align="center">
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width:600px;background:#FFFFFF;border-radius:12px;overflow:hidden;border:1px solid #E5E7EB;box-shadow:0 4px 12px rgba(0,0,0,0.05);">
<tr><td style="background:#0B1D3A;padding:32px 24px;text-align:center;"><a href="{WEBSITE_LINK}" target="_blank"><img src="{LOGO_URL}" alt="" height="36" style="display:block;margin:0 auto;height:36px;width:auto;"></a></td></tr>
<tr><td style="padding:28px 24px 16px 24px;"><h2 style="color:#0F172A;margin:0 0 8px;font-size:20px;font-weight:800;">Price Drops Detected</h2><p style="color:#64748B;margin:0;font-size:14px;line-height:1.5;">Items on your tracked watchlists have dropped in price. Here are today's verified deals:</p></td></tr>
<tr><td style="padding:8px 24px 24px 24px;">
"""

    for d in deal_list:
        if d["percent"] >= 25 or d["save"] >= 100:
            badge_text = f'{GOLD_DIAMOND_SVG}<span style="vertical-align:middle;">WHALE DEAL</span>'
            badge_bg = "#FF7F50"
        elif d["percent"] >= 15 or d["save"] >= 50:
            # ---> Added the spinning SVG to the MEGA DROP right here <---
            badge_text = f'{GOLD_DIAMOND_SVG}<span style="vertical-align:middle;">MEGA DROP</span>'
            badge_bg = "#DC2626"
        else:
            badge_text = '<span style="vertical-align:middle;">🏷️ PRICE DROP</span>'
            badge_bg = "#0B1D3A"

        text_body += f"[{d['percent']}% OFF] {d['title']}\nWas: ${d['was']:.2f} | Now: ${d['now']:.2f} (Save {d['percent']}%)\nLink: {d['link']}\n\n"
        
        image_html = f'<div style="margin:12px 0 16px 0;text-align:center;"><a href="{d["link"]}" target="_blank"><img src="{d["image"]}" alt="{d["title"]}" width="160" style="max-width:160px;max-height:160px;height:auto;border-radius:8px;border:1px solid #E2E8F0;margin:0 auto;display:block;"></a></div>' if d["image"] else ""
        button_link = d["image"] if d["image"] else d["link"]

        html_content += f"""
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:20px;border:1px solid #E2E8F0;border-radius:10px;background:#FFFFFF;box-shadow:0 1px 3px rgba(0,0,0,0.03);">
<tr><td style="padding:20px;">
<div style="margin-bottom:12px;">
  <span style="background:{badge_bg};color:#FFFFFF;font-size:11px;font-weight:700;padding:6px 14px;border-radius:6px;text-transform:uppercase;letter-spacing:0.8px;display:inline-block;">
    {badge_text}
  </span>
</div>
{image_html}
<a href="{d['link']}" target="_blank" style="color:#0F172A;text-decoration:none;font-size:15px;font-weight:700;line-height:1.4;display:block;margin-bottom:16px;">{d['title']}</a>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom:18px;"><tr>
<td style="font-size:13px;color:#EF4444;font-weight:700;">Was: <span style="text-decoration:line-through;color:#EF4444;font-weight:700;">${d['was']:.2f}</span></td>
<td align="right"><span style="font-size:20px;font-weight:800;color:#0F172A;">${d['now']:.2f}</span>
<span style="background:#DCFCE7;color:#166534;font-size:11px;font-weight:600;padding:4px 8px;border-radius:4px;margin-left:8px;">Save {d['percent']}%</span></td>
</tr></table>
<a href="{button_link}" target="_blank" style="display:block;width:100%;background:#0B1D3A;color:#FFFFFF;text-align:center;padding:12px 0;border-radius:6px;font-size:12px;font-weight:600;text-transform:uppercase;letter-spacing:0.8px;text-decoration:none;">VIEW DEAL ON EBAY →</a>
</td></tr></table>"""

    text_body += f"-" * 45 + f"\nUpgrade to Premium: {PREMIUM_LINK}\nManage preferences: {WEBSITE_LINK}"

    html_content += f"""</td></tr>
<tr><td style="padding:0 24px 28px 24px;"><div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:10px;padding:20px;text-align:center;"><p style="margin:0 0 12px;font-size:13px;color:#475569;line-height:1.4;">Want to track a specific item? Upgrade to Premium and we'll watch it daily for you.</p><a href="{PREMIUM_LINK}" target="_blank" style="display:inline-block;background:#0B1D3A;color:#FFFFFF;padding:10px 24px;border-radius:6px;font-size:13px;font-weight:600;text-decoration:none;">Upgrade to Premium – $3/mo</a></div></td></tr>
<tr><td style="background:#0B1D3A;padding:24px;text-align:center;border-top:1px solid #1E293B;"><a href="{WEBSITE_LINK}" target="_blank" style="color:#60A5FA;font-size:12px;text-decoration:underline;">Manage Preferences & Watchlists</a></td></tr></table></td></tr></table></body></html>"""

    subscribers = load_subscribers()
    if not subscribers:
        print("No subscribers.")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, PASSWORD)
        for sub in subscribers:
            if "To" in msg:
                msg.replace_header("To", sub)
            else:
                msg["To"] = sub
            server.send_message(msg)
            print(f"Alert sent to {sub}")


def send_daily_beacon(drops, product_count):
    if drops is None:
        drop_count = "N/A"
    else:
        drop_count = len(drops) if not drops.empty else 0

    subject = "Dealkly Daily Report – Pipeline Ran Successfully"
    body = f"Daily scraping report.\n\nProducts scraped today: {product_count}\nPrice drops detected (unfiltered): {drop_count}\n"
    if drops is not None and not drops.empty:
        body += "\nAll drops (unfiltered):\n"
        for _, row in drops.iterrows():
            drop_percent = round((-row["drop"] / row["price_yest"]) * 100)
            body += f"- {row['title']}: ${row['price_yest']:.2f} → ${row['price_today']:.2f} ({drop_percent}%)\n"
    body += f"\n—\nDealkly\nhttps://dealkly.github.io/deal-alerts/"

    msg = MIMEMultipart()
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["To"] = SENDER
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, PASSWORD)
        server.send_message(msg)
        print("Daily report sent to admin.")


if __name__ == "__main__":
    drops, product_count = detect_price_drops()
    send_alert(drops)
    send_daily_beacon(drops, product_count)

    if ADMIN_TEST_MODE:
        print("Admin test mode – sending sample HTML email.")
        sample = build_sample_deal_html()
        subscribers = load_subscribers()
        if subscribers:
            msg = MIMEMultipart()
            msg["From"] = f"{SENDER_NAME} <{SENDER}>"
            msg["Subject"] = "💎 Dealkly Admin Test – Pipeline Healthy"
            msg.attach(MIMEText(sample, "html"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SENDER, PASSWORD)
                for sub in subscribers:
                    if "To" in msg:
                        msg.replace_header("To", sub)
                    else:
                        msg["To"] = sub
                    server.send_message(msg)
                    print(f"Sample HTML alert sent to {sub}")
        sys.exit(0)
