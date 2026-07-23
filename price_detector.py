import pandas as pd
import json
import smtplib
import os
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
# --------------------------------------------

def load_subscribers():
    with open(SUBSCRIBERS_FILE, "r") as f:
        data = json.load(f)
    return data

def detect_price_drops():
    if not os.path.exists(YESTERDAY_CSV):
        print("No yesterday data found. Skipping comparison (first run).")
        return None

    yest = pd.read_csv(YESTERDAY_CSV)
    today = pd.read_csv(TODAY_CSV)

    # Merge on title, keep price columns and links (use today's link)
    merged = pd.merge(yest, today, on="title", suffixes=("_yest", "_today"))
    
    # If link column exists in today's CSV, it will appear as link_today; otherwise we create a fallback
    if "link_today" not in merged.columns and "link" in today.columns:
        merged["link_today"] = today.set_index("title")["link"].reindex(merged["title"]).values
        
    merged["drop"] = merged["price_today"] - merged["price_yest"]
    drops = merged[merged["drop"] < 0]
    return drops

def send_alert(drops):
    if drops is None:
        print("No comparison performed. Exiting gracefully.")
        return

        if drops.empty:
        print("No price drops today. Sending test email.")
        # Temporary test – will send email anyway
        subscribers = load_subscribers()
        if subscribers:
            msg = MIMEMultipart()
            msg["From"] = f"{SENDER_NAME} <{SENDER}>"
            msg["Subject"] = "Dealkly Test – Pipeline Working"
            body = "This is a test email. The Dealkly pipeline ran successfully and detected no price drops today."
            msg.attach(MIMEText(body, "plain"))
            with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
                server.login(SENDER, PASSWORD)
                for subscriber in subscribers:
                    msg["To"] = subscriber
                    server.send_message(msg)
                    print(f"Test email sent to {subscriber}")
        return
    subject = "Dealkly Alert: Price Drop Detected"
    body = "A product you’re tracking just got cheaper.\n\n"
    for _, row in drops.iterrows():
        # Get the product link (prefer today's link if available)
        link = row.get("link_today", row.get("link_yest", "https://www.ebay.com"))
        body += f"{row['title']}\n"
        body += f"Was: ${row['price_yest']:.2f} → Now: ${row['price_today']:.2f} (save ${-row['drop']:.2f})\n"
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
            # Safely replace the header so emails remain 100% private
            if "To" in msg:
                msg.replace_header("To", subscriber)
            else:
                msg["To"] = subscriber
                
            server.send_message(msg)
            print(f"Alert sent to {subscriber}")

if __name__ == "__main__":
    drops = detect_price_drops()
    send_alert(drops)
