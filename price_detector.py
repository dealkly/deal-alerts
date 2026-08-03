import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import pandas as pd

# ==========================================
# CONFIGURATION & CONSTANTS
# ==========================================
SENDER = os.getenv("SENDER_EMAIL", "alerts@dealkly.com")
SENDER_NAME = "Dealkly Alerts"
PASSWORD = os.getenv("SMTP_PASSWORD", "")
MIN_DROP_PERCENT = 10.0  # Minimum percentage drop to trigger email
MIN_ITEM_PRICE = 5.00    # Minimum item price threshold to exclude low-value items

# URL for your uploaded white logo on GitHub
LOGO_URL = "https://dealkly.github.io/deal-alerts/logo_white.png"
PREMIUM_LINK = "https://dealkly.gumroad.com/l/premium-alerts"
WEBSITE_LINK = "https://dealkly.github.io/deal-alerts/"


def load_subscribers():
    """
    Placeholder subscriber loader function.
    Replace or connect to your database/CSV reader as needed.
    """
    return os.getenv("SUBSCRIBER_LIST", "").split(",") if os.getenv("SUBSCRIBER_LIST") else []


def send_alert(drops: pd.DataFrame) -> None:
    """
    Filters price drops, deduplicates by URL, builds dual-format text/HTML email,
    and dispatches notifications to subscribed users via SMTP_SSL.
    """
    if drops is None:
        print("[INFO] No comparison dataframe provided. Exiting process.")
        return

    if drops.empty:
        print("[INFO] Zero price drops detected today.")
        return

    # -------------------------------------------------------------------------
    # 1. QUALITY & THRESHOLD FILTERING
    # -------------------------------------------------------------------------
    filtered = drops[
        ((-drops["drop"] / drops["price_yest"]) * 100 >= MIN_DROP_PERCENT) &
        (drops["price_today"] >= MIN_ITEM_PRICE)
    ]

    if filtered.empty:
        print(f"[INFO] No drops met the quality criteria (>= {MIN_DROP_PERCENT}% drop & >= ${MIN_ITEM_PRICE:.2f}).")
        return

    # -------------------------------------------------------------------------
    # 2. DEDUPLICATION & METRIC COMPUTATION
    # -------------------------------------------------------------------------
    best_deal = {}
    for _, row in filtered.iterrows():
        url = row.get("link_today", row.get("link_yest", ""))
        if not url:
            continue

        drop_val = -row["drop"] if row["drop"] < 0 else row["drop"]
        percent = round((drop_val / row["price_yest"]) * 100)
        image_url = row.get("image", row.get("image_url", row.get("img", "")))

        # Retain the highest percentage drop if duplicate URLs exist
        if url not in best_deal or percent > best_deal[url]["percent"]:
            best_deal[url] = {
                "title": str(row["title"]).strip(),
                "was": float(row["price_yest"]),
                "now": float(row["price_today"]),
                "save": float(drop_val),
                "percent": int(percent),
                "link": str(url).strip(),
                "image": str(image_url).strip() if pd.notna(image_url) else ""
            }

    if not best_deal:
        print("[INFO] No valid deals remaining after link parsing.")
        return

    # Sort deal listings in descending order by savings percentage
    deal_list = sorted(best_deal.values(), key=lambda x: x["percent"], reverse=True)

    # -------------------------------------------------------------------------
    # 3. BUILD DUAL-FORMAT EMAIL CONTENT
    # -------------------------------------------------------------------------
    subject = "💎 Dealkly Alert: Verified Price Drops Detected"

    # A. Plain-Text Fallback (For accessibility, smartwatch previews, and spam filtering)
    text_body = "DEALKLY ALERTS - VERIFIED PRICE DROPS DETECTED\n"
    text_body += "=" * 45 + "\n\n"
    text_body += "Items on your tracked list have dropped in price:\n\n"

    # B. HTML Base Template (Using Inline Table-Based Layouts for Email Clients)
    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="X-UA-Compatible" content="IE=edge">
    <title>Dealkly Alert</title>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap');
        body {{ margin: 0; padding: 0; background-color: #F4F6F8; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; }}
        table {{ border-collapse: collapse; }}
        img {{ border: 0; height: auto; line-height: 100%; outline: none; text-decoration: none; display: block; }}
    </style>
</head>
<body style="margin: 0; padding: 0; background-color: #F4F6F8;">
    <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #F4F6F8; padding: 24px 0;">
        <tr>
            <td align="center">
                <!-- Main Container -->
                <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="max-width: 600px; background-color: #FFFFFF; border-radius: 12px; overflow: hidden; border: 1px solid #E5E7EB; box-shadow: 0 4px 12px rgba(0, 0, 0, 0.05);">
                    
                    <!-- Top Sandwich Framing: Dark Navy Header with Standalone White Logo -->
                    <tr>
                        <td style="background-color: #0B1D3A; padding: 32px 24px; text-align: center;">
                            <a href="{WEBSITE_LINK}" target="_blank" style="text-decoration: none; display: inline-block;">
                                <!-- Note: alt="" ensures no extra text is shown if the image fails to load -->
                                <img src="{LOGO_URL}" alt="" height="36" style="display: block; margin: 0 auto; height: 36px; width: auto; border: 0;">
                            </a>
                        </td>
                    </tr>
                    
                    <!-- Sub-header Text -->
                    <tr>
                        <td style="padding: 28px 24px 16px 24px; background-color: #FFFFFF;">
                            <h2 style="color: #0F172A; margin: 0 0 8px 0; font-size: 20px; font-weight: 800; letter-spacing: -0.4px;">Price Drops Detected</h2>
                            <p style="color: #64748B; margin: 0; font-size: 14px; line-height: 1.5;">Items on your tracked watchlists have dropped in price. Here are today's verified deals:</p>
                        </td>
                    </tr>
                    
                    <!-- Product Cards Container -->
                    <tr>
                        <td style="padding: 8px 24px 24px 24px;">
"""

    # Dynamically inject product cards into Plain Text and HTML templates
    for d in deal_list:
        # Determine badge thresholds and color mapping
        if d["percent"] >= 25 or d["save"] >= 100:
            badge_text = "💎 WHALE DEAL"
            badge_bg = "#FF7F50"      # Coral
        elif d["percent"] >= 15 or d["save"] >= 50:
            badge_text = "🚨 MEGA DROP"
            badge_bg = "#DC2626"      # Red
        else:
            badge_text = "PRICE DROP"
            badge_bg = "#0B1D3A"      # Navy

        # Append to Text Template
        text_body += f"[{badge_text}] {d['title']}\n"
        text_body += f"Was: ${d['was']:.2f} | Now: ${d['now']:.2f} (Save {d['percent']}%)\n"
        text_body += f"Link: {d['link']}\n\n"

        # Construct Product Image HTML Block if valid URL is present
        image_html = ""
        if d["image"]:
            image_html = f"""
            <div style="margin: 12px 0 16px 0; text-align: center;">
                <a href="{d['link']}" target="_blank">
                    <img src="{d['image']}" alt="{d['title']}" width="140" style="max-width: 140px; height: auto; border-radius: 8px; border: 1px solid #E2E8F0; margin: 0 auto; display: block;">
                </a>
            </div>
            """

        # Append Card HTML
        html_content += f"""
                            <!-- Individual Product Card -->
                            <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 20px; border: 1px solid #E2E8F0; border-radius: 10px; background-color: #FFFFFF; box-shadow: 0 1px 3px rgba(0,0,0,0.03);">
                                <tr>
                                    <td style="padding: 20px;">
                                        <!-- Tier Badge -->
                                        <div style="margin-bottom: 12px;">
                                            <span style="background-color: {badge_bg}; color: #FFFFFF; font-size: 10px; font-weight: 800; padding: 4px 10px; border-radius: 4px; text-transform: uppercase; letter-spacing: 0.8px; display: inline-block;">
                                                {badge_text}
                                            </span>
                                        </div>
                                        
                                        <!-- Optional Image -->
                                        {image_html}
                                        
                                        <!-- Product Title Link -->
                                        <a href="{d['link']}" target="_blank" style="color: #0F172A; text-decoration: none; font-size: 15px; font-weight: 700; line-height: 1.4; display: block; margin-bottom: 16px;">
                                            {d['title']}
                                        </a>
                                        
                                        <!-- Financial Summary Grid -->
                                        <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin-bottom: 18px;">
                                            <tr>
                                                <td style="font-size: 13px; color: #94A3B8;">
                                                    Was: <span style="text-decoration: line-through; color: #94A3B8;">${d['was']:.2f}</span>
                                                </td>
                                                <td align="right">
                                                    <span style="font-size: 20px; font-weight: 800; color: #0F172A;">${d['now']:.2f}</span>
                                                    <span style="background-color: #DCFCE7; color: #166534; font-size: 11px; font-weight: 800; padding: 4px 8px; border-radius: 4px; margin-left: 8px; display: inline-block;">
                                                        Save {d['percent']}%
                                                    </span>
                                                </td>
                                            </tr>
                                        </table>
                                        
                                        <!-- Primary Call to Action Button -->
                                        <a href="{d['link']}" target="_blank" style="display: block; width: 100%; background-color: #0B1D3A; color: #FFFFFF; text-align: center; padding: 12px 0; border-radius: 6px; font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 0.8px; text-decoration: none;">
                                            VIEW DEAL ON EBAY &rarr;
                                        </a>
                                    </td>
                                </tr>
                            </table>
"""

    # Append Plain Text Footer
    text_body += "-" * 45 + "\n"
    text_body += f"Want custom watchlist alerts? Upgrade to Premium: {PREMIUM_LINK}\n"
    text_body += f"Manage preferences: {WEBSITE_LINK}\n"
    text_body += "Dealkly Alerts — Automated Price Detection Engine"

    # Append HTML Footer with Upsell Card & Bottom Sandwich Header
    html_content += f"""
                        </td>
                    </tr>
                    
                    <!-- Monetization / Premium Upsell Banner -->
                    <tr>
                        <td style="padding: 0 24px 28px 24px; background-color: #FFFFFF;">
                            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 10px; padding: 20px; text-align: center;">
                                <p style="margin: 0 0 12px 0; font-size: 13px; color: #475569; line-height: 1.4;">Want to track a specific item? Upgrade to Premium and we'll watch it daily for you.</p>
                                <a href="{PREMIUM_LINK}" target="_blank" style="display: inline-block; background-color: #0B1D3A; color: #FFFFFF; padding: 10px 24px; border-radius: 6px; font-size: 13px; font-weight: 700; text-decoration: none;">Upgrade to Premium – $3/mo</a>
                            </div>
                        </td>
                    </tr>
                    
                    <!-- Bottom Sandwich Framing: Dark Navy Footer -->
                    <tr>
                        <td style="background-color: #0B1D3A; padding: 32px 24px; text-align: center; border-top: 1px solid #1E293B;">
                            <p style="color: #FFFFFF; font-size: 14px; font-weight: 800; margin: 0 0 6px 0; letter-spacing: 0.5px;">Dealkly Alerts</p>
                            <p style="color: #94A3B8; font-size: 12px; margin: 0 0 16px 0;">Automated deal tracking engine. No spam, just price drops.</p>
                            <a href="{WEBSITE_LINK}" target="_blank" style="color: #60A5FA; font-size: 12px; text-decoration: underline;">Manage Preferences & Watchlists</a>
                        </td>
                    </tr>
                </table>
            </td>
        </tr>
    </table>
</body>
</html>
"""

    # -------------------------------------------------------------------------
    # 4. DISPATCHING & SMTP TRANSPORT
    # -------------------------------------------------------------------------
    subscribers = load_subscribers()
    if not subscribers:
        print("[WARNING] Subscriber list is empty. Aborting email dispatch.")
        return

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["Subject"] = subject

    # Attach both parts (Email client renders HTML by default, text as fallback)
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_content, "html"))

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(SENDER, PASSWORD)
            for subscriber in subscribers:
                subscriber_clean = subscriber.strip()
                if not subscriber_clean:
                    continue
                    
                if "To" in msg:
                    msg.replace_header("To", subscriber_clean)
                else:
                    msg["To"] = subscriber_clean
                    
                server.send_message(msg)
                print(f"[SUCCESS] Alert dispatched successfully to: {subscriber_clean}")
    except Exception as e:
        print(f"[ERROR] Failed to send email via SMTP server: {e}")
