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

# Admin test mode via workflow_dispatch password
ADMIN_PASSWORD_INPUT = os.environ.get("ADMIN_PASSWORD_INPUT", "")
ADMIN_SECRET = os.environ.get("ADMIN_SECRET", "")
ADMIN_TEST_MODE = (ADMIN_PASSWORD_INPUT == ADMIN_SECRET) and ADMIN_SECRET != ""
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

    merged = pd.merge(yest, today, on="title", suffixes=("_yest", "_today"))
    
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
        print("No price drops today.")
        return

    subject = "Dealkly Alert: Price Drop Detected"
    body = "A product you’re tracking just got cheaper.\n\n"
    for _, row in drops.iterrows():
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
            if "To" in msg:
                msg.replace_header("To", subscriber)
            else:
                msg["To"] = subscriber
            server.send_message(msg)
            print(f"Alert sent to {subscriber}")

if __name__ == "__main__":
    drops = detect_price_drops()
    send_alert(drops)

    # Admin live button: send test email only if correct password provided
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
