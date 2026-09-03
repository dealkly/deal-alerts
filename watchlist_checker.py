import json
import pandas as pd
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# --- CONFIGURATION ---
WATCHLIST_FILE = "watchlist.json"
TODAY_CSV = "books_today.csv"
SENDER = "dealkly.contact@gmail.com"
SENDER_NAME = "Dealkly Alerts"
PASSWORD = os.environ.get("GMAIL_APP_PASSWORD")
PREMIUM_URL = "https://dealkly.gumroad.com/l/premium-alerts"
WEBSITE_LINK = "https://dealkly.github.io/deal-alerts/"
CONTACT_LINK = "https://dealkly.github.io/deal-alerts/contact.html"
# ---------------------

if not PASSWORD:
    raise ValueError("GMAIL_APP_PASSWORD environment variable not set.")


def load_watchlist():
    if not os.path.exists(WATCHLIST_FILE):
        return []

    with open(WATCHLIST_FILE, "r") as f:
        data = json.load(f)

    if isinstance(data, list):
        return data

    return []


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

        try:
            matches = deals_df[deals_df["title"].str.contains(pattern, case=False, na=False)]
        except Exception as e:
            print(f"Watchlist matching error for {email}: {e}")
            continue

        if not matches.empty:
            notifications.append((email, matches))

    return notifications


def send_watchlist_email(subscriber_email, matched_deals):
    total = len(matched_deals)
    subject = f"[Dealkly] {total} Personalized Deal Alert" if total == 1 else f"[Dealkly] {total} Personalized Deal Alerts"

    body = f"Dealkly found {total} deal(s) matching the watchlist.\n\n"

    for _, row in matched_deals.iterrows():
        body += f"• {row['title']}\n"

        try:
            body += f"  Total cost: ${float(row['price']):.2f}\n"
        except Exception:
            body += f"  Total cost: {row.get('price', 'N/A')}\n"

        body += f"  Link: {row.get('link', '')}\n\n"

    body += "—\n"
    body += "Want to track more items? Upgrade to Premium:\n"
    body += f"{PREMIUM_URL}\n\n"
    body += f"Dealkly: {WEBSITE_LINK}\n"
    body += f"Contact: {CONTACT_LINK}\n"

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
        print("Watchlist is empty. No personalized alerts to send.")
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
