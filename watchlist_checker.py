import json
import pandas as pd
import smtplib
import os
import re
import uuid
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
WATCHLIST_FILE = "watchlist.json"
PAID_FILE = "paid_subscribers.json"
TODAY_CSV = "books_today.csv"
YESTERDAY_CSV = "books_yesterday.csv"

SENDER = "dealkly.contact@gmail.com"
SENDER_NAME = "Dealkly Alerts"
PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")

WEBSITE_LINK = "https://dealkly.github.io/deal-alerts/"
UNSUBSCRIBE_LINK = "https://dealkly.github.io/deal-alerts/account.html"
CONTACT_LINK = "https://dealkly.github.io/deal-alerts/contact.html"
# ---------------------

if not PASSWORD:
    raise ValueError("GMAIL_APP_PASSWORD environment variable not set.")

def load_json(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, "r") as f:
        data = json.load(f)
    return data if isinstance(data, list) else []

def load_csv(filename):
    if not os.path.exists(filename):
        return pd.DataFrame()
    return pd.read_csv(filename)

def find_premium_drops(today_df, yesterday_df):
    """Compare today and yesterday, filter to premium, and return actual drops."""
    if today_df.empty or yesterday_df.empty:
        return pd.DataFrame()

    # Filter to premium items only (assuming test_engine.py adds a 'source' column)
    if 'source' in today_df.columns:
        today_prem = today_df[today_df['source'] == 'premium'].copy()
        yesterday_prem = yesterday_df[yesterday_df['source'] == 'premium'].copy()
    else:
        print("Warning: 'source' column missing. Assuming all items are premium for this test.")
        today_prem = today_df.copy()
        yesterday_prem = yesterday_df.copy()

    if today_prem.empty or yesterday_prem.empty:
        return pd.DataFrame()

    # Merge on title to find items present both days
    merged = pd.merge(today_prem, yesterday_prem, on='title', suffixes=('_today', '_yesterday'))

    # Find actual price drops
    merged['price_today'] = pd.to_numeric(merged['price_today'], errors='coerce')
    merged['price_yesterday'] = pd.to_numeric(merged['price_yesterday'], errors='coerce')
    
    drops = merged[merged['price_today'] < merged['price_yesterday']].copy()
    
    # Calculate savings
    drops['discount'] = drops['price_yesterday'] - drops['price_today']
    
    return drops

def build_email_html(matched_deals):
    """Build the branded HTML email."""
    
    rows_html = ""
    for _, row in matched_deals.iterrows():
        title = row.get('title', 'Unknown Item')
        price_today = row['price_today']
        price_yesterday = row['price_yesterday']
        link = row.get('link_today', row.get('link', '#'))
        image = row.get('image_today', row.get('image', ''))
        keyword = row.get('keyword', 'Your Watchlist')

        image_html = f'<img src="{image}" alt="Item" style="width: 100px; height: 100px; object-fit: cover; border-radius: 8px; margin-right: 15px;">' if image else ''

        rows_html += f"""
        <div style="border: 1px solid #FDE68A; border-radius: 12px; padding: 15px; margin-bottom: 15px; background-color: #FFFDF7; display: flex; align-items: center;">
            {image_html}
            <div style="flex-grow: 1;">
                <p style="margin: 0 0 5px 0; font-size: 11px; font-weight: bold; color: #B45309; text-transform: uppercase;">Matched: {keyword}</p>
                <h3 style="margin: 0 0 8px 0; font-size: 16px; color: #1D2023;"><a href="{link}" style="color: #1D2023; text-decoration: none;">{title}</a></h3>
                <p style="margin: 0; font-size: 14px; color: #64748b;">
                    <span style="text-decoration: line-through;">${price_yesterday:.2f}</span> 
                    <strong style="color: #D97706; font-size: 18px; margin-left: 8px;">${price_today:.2f}</strong>
                </p>
            </div>
        </div>
        """

    html = f"""
    <!DOCTYPE html>
    <html>
    <body style="font-family: 'Inter', system-ui, sans-serif; background-color: #F5EFE6; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background: #ffffff; border-radius: 16px; overflow: hidden; box-shadow: 0 4px 6px rgba(0,0,0,0.05);">
            <div style="background: linear-gradient(135deg, #92400E, #78350F); padding: 30px 20px; text-align: center;">
                <h1 style="color: #ffffff; margin: 0; font-size: 24px;">Dealkly Premium Alert</h1>
                <p style="color: #FDE68A; margin: 5px 0 0 0; font-size: 14px;">A specific item on your watchlist just dropped.</p>
            </div>
            <div style="padding: 30px 20px;">
                {rows_html}
                
                <div style="text-align: center; margin-top: 30px;">
                    <a href="{WEBSITE_LINK}" style="display: inline-block; background: linear-gradient(135deg, #D97706, #B45309); color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 8px; font-weight: bold;">Browse Live Deals</a>
                </div>
            </div>
            <div style="background: #FFFDF7; padding: 20px; text-align: center; border-top: 1px solid #FDE68A; font-size: 12px; color: #64748b;">
                <p style="margin: 0 0 10px 0;">You are receiving this because you are a Premium subscriber on Dealkly.</p>
                <p style="margin: 0;">
                    <a href="{UNSUBSCRIBE_LINK}" style="color: #92400E;">Manage Account</a> | 
                    <a href="{CONTACT_LINK}" style="color: #92400E;">Contact Support</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """
    return html

def send_watchlist_email(subscriber_email, matched_deals):
    total = len(matched_deals)
    subject = f"[Dealkly] {total} Watchlist Alert" if total == 1 else f"[Dealkly] {total} Watchlist Alerts"
    
    # Unique Message-ID to prevent Gmail threading
    msg_id = f"<{uuid.uuid4().hex}.{datetime.now().strftime('%Y%m%d%H%M%S')}@dealkly.github.io>"
    
    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["To"] = subscriber_email
    msg["Subject"] = subject
    msg["Message-ID"] = msg_id
    msg["Precedence"] = "bulk"
    
    # Required Unsubscribe Headers
    msg["List-Unsubscribe"] = f"<{UNSUBSCRIBE_LINK}>"
    msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

    html_body = build_email_html(matched_deals)
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, PASSWORD)
        server.send_message(msg)
        print(f"Watchlist alert sent to {subscriber_email}")

def main():
    watchlist = load_json(WATCHLIST_FILE)
    paid_users = load_json(PAID_FILE)

    if not watchlist:
        print("Watchlist is empty. No personalized alerts to send.")
        return
        
    if not paid_users:
        print("No paid users found. Skipping.")
        return

    today_df = load_csv(TODAY_CSV)
    yesterday_df = load_csv(YESTERDAY_CSV)

    if today_df.empty or yesterday_df.empty:
        print("Missing CSV data (today or yesterday). Watchlist check skipped.")
        return

    # Find all drops today for premium items
    drops_df = find_premium_drops(today_df, yesterday_df)

    if drops_df.empty:
        print("No premium items dropped today.")
        return

    # Check each subscriber
    for entry in watchlist:
        email = entry.get("email")
        keywords = entry.get("keywords", [])

        if not email or not keywords:
            continue
            
        # Only email people who are actually paying
        if email not in paid_users:
            continue

        # Build safe regex pattern
        escaped_keywords = [re.escape(kw) for kw in keywords]
        pattern = "|".join(escaped_keywords)

        # Find matches for this specific user
        try:
            matches = drops_df[drops_df["title"].str.contains(pattern, case=False, na=False)]
        except Exception as e:
            print(f"Watchlist matching error for {email}: {e}")
            continue

        if not matches.empty:
            send_watchlist_email(email, matches)

if __name__ == "__main__":
    main()
