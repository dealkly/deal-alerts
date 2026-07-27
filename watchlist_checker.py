import json
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import os

# --- CONFIGURATION ---
WATCHLIST_FILE = "watchlist.json"
TODAY_CSV = "books_today.csv"
SENDER = "dealkly.contact@gmail.com"
SENDER_NAME = "Dealkly Alerts"
PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
PREMIUM_URL = "https://dealkly.gumroad.com/l/premium-alerts"
# ---------------------

def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return []
    with open(WATCHLIST_FILE, "r") as f:
        return json.load(f)

def load_todays_deals():
    if not os.path.exists(TODAY_CSV):
        return pd.DataFrame()
    return pd.read_csv(TODAY_CSV)

def check_watchlist(deals_df, watchlist):
    """Return a list of (subscriber_email, matched_rows) tuples."""
    notifications = []
    for entry in watchlist:
        email = entry.get("email")
        keywords = entry.get("keywords", [])
        if not email or not keywords:
            continue
        pattern = "|".join(keywords)
        matches = deals_df[deals_df["title"].str.contains(pattern, case=False, na=False)]
        if not matches.empty:
            notifications.append((email, matches))
    return notifications

def send_watchlist_email(subscriber_email, matched_deals):
    subject = "🎯 Your Personalised Deal Alert – Dealkly"
    body = f"We found {len(matched_deals)} deal(s) matching your watchlist:\n\n"
    for _, row in matched_deals.iterrows():
        body += f"• {row['title']}\n"
        body += f"  Total cost: ${row['price']:.2f}\n"
        body += f"  Link: {row.get('link', '')}\n\n"
    body += "—\n"
    body += "Want to track unlimited items? Upgrade to Premium:\n"
    body += f"{PREMIUM_URL}\n\n"
    body += "If you no longer wish to receive these alerts, please unsubscribe."

    msg = MIMEMultipart()
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["To"] = subscriber_email
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, PASSWORD)
        server.send_message(msg)
        print(f"Watchlist alert sent to {subscriber_email}")

def main():
    watchlist = load_watchlist()
    if not watchlist:
        print("Watchlist is empty. No personalised alerts to send.")
        return

    deals_df = load_todays_deals()
    if deals_df.empty:
        print("No deals scraped today. Watchlist check skipped.")
        return

    notifications = check_watchlist(deals_df, watchlist)
    if not notifications:
        print("No watchlist matches today.")
        return

    for email, matches in notifications:
        send_watchlist_email(email, matches)

if __name__ == "__main__":
    main()
