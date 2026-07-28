import pandas as pd
import json
import smtplib
import os
import sys
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ------------------ CONFIG ------------------
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

# ---------- QUALITY FILTERS ----------
MIN_DROP_PERCENT = 10.0      # only alert if price dropped by at least 10%
MIN_ITEM_PRICE = 5.00        # only track items with total price >= $5 (adjustable)
# --------------------------------------------

def load_subscribers():
    with open(SUBSCRIBERS_FILE, "r") as f:
        data = json.load(f)
    return data

def get_deal_tag(drop_amount, price_yest):
    """Return a tag string if the deal is exceptional."""
    percent = (-drop_amount / price_yest) * 100
    # WHALE DEAL: 25%+ off OR save $100 or more
    if percent >= 25 or -drop_amount >= 100:
        return "💎 WHALE DEAL"
    # MEGA DROP: 15%+ off OR save $50 or more
    elif percent >= 15 or -drop_amount >= 50:
        return "🚨 MEGA DROP"
    return ""

def detect_price_drops():
    if not os.path.exists(YESTERDAY_CSV):
        print("No yesterday data found. Skipping comparison (first run).")
        return None, 0

    yest = pd.read_csv(YESTERDAY_CSV)
    today = pd.read_csv(TODAY_CSV)
    product_count = len(today)

    merged = pd.merge(yest, today, on="title", suffixes=("_yest", "_today"))
    
    if "link_today" not in merged.columns and "link" in today.columns:
        merged["link_today"] = today.set_index("title")["link"].reindex(merged["title"]).values
        
    merged["drop"] = merged["price_today"] - merged["price_yest"]
    drops = merged[merged["drop"] < 0]
    return drops, product_count

def send_alert(drops):
    if drops is None:
        print("No comparison performed. Exiting gracefully.")
        return

    if drops.empty:
        print("No price drops today.")
        return

    # Apply percentage-based drop filter and minimum price
    filtered = drops[
        ((-drops["drop"] / drops["price_yest"]) * 100 >= MIN_DROP_PERCENT) &
        (drops["price_today"] >= MIN_ITEM_PRICE)
    ]

    if filtered.empty:
        print(f"No price drops pass quality filters (min {MIN_DROP_PERCENT}% drop, min price ${MIN_ITEM_PRICE:.2f}).")
        return

    subject = "Dealkly Alert: Price Drop Detected"
    body = "A product you’re tracking just got cheaper.\n\n"
    for _, row in filtered.iterrows():
        link = row.get("link_today", row.get("link_yest", "https://www.ebay.com"))
        drop_percent = round((-row["drop"] / row["price_yest"]) * 100)
        tag = get_deal_tag(row["drop"], row["price_yest"])
        if tag:
            body += f"{tag} {row['title']}\n"
        else:
            body += f"{row['title']}\n"
        body += f"Was: ${row['price_yest']:.2f} → Now: ${row['price_today']:.2f} (save {drop_percent}%)\n"
        body += f"View it here: {link}\n\n"
        
    body += "—\nDealkly Alerts\nhttps://dealkly.github.io/deal-alerts/"

    subscribers = load_subscribers()
    if not subscribers:
        print("No subscribers. Email not sent.")
        return

    msg = MIMEMultipart()
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, PASSWORD)
        for subscriber in subscribers:
            if "To" in msg:
                msg.replace_header("To", subscriber)
            else:
                msg["To"] = subscriber
            server.send_message(msg)
            print(f"Alert sent to {subscriber}")

def send_daily_beacon(drops, product_count):
    if drops is None:
        drop_count = "N/A (no comparison data)"
        total_drops = 0
    else:
        total_drops = len(drops) if not drops.empty else 0
        drop_count = total_drops

    subject = "Dealkly Daily Report – Pipeline Ran Successfully"
    body = (
        f"Daily scraping report.\n\n"
        f"Products scraped today: {product_count}\n"
        f"Price drops detected (unfiltered): {drop_count}\n"
    )
    if drops is not None and not drops.empty:
        body += "\nAll drops (unfiltered):\n"
        for _, row in drops.iterrows():
            drop_percent = round((-row["drop"] / row["price_yest"]) * 100)
            body += f"- {row['title']}: ${row['price_yest']:.2f} → ${row['price_today']:.2f} ({drop_percent}%)\n"
    body += f"\n—\nDealkly Alerts\nhttps://dealkly.github.io/deal-alerts/"

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
        print("Admin test mode activated – sending test email.")
        subscribers = load_subscribers()
        if subscribers:
            msg = MIMEMultipart()
            msg["From"] = f"{SENDER_NAME} <{SENDER}>"
            msg["Subject"] = "Dealkly Admin Test – Pipeline Healthy"
            body = "This is a manual admin test. The Dealkly pipeline is working correctly."
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SENDER, PASSWORD)
                for subscriber in subscribers:
                    if "To" in msg:
                        msg.replace_header("To", subscriber)
                    else:
                        msg["To"] = subscriber
                    server.send_message(msg)
                    print(f"Admin test email sent to {subscriber}")
        else:
            print("No subscribers to send test to.")
        sys.exit(0)
