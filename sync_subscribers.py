import os
import json
import re
import smtplib
import requests
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

GUMROAD_ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")

PAID_FILE = "paid_subscribers.json"
WATCHLIST_FILE = "watchlist.json"
SETUP_EMAIL_FILE = "premium_setup_sent.json"

SENDER = "dealkly.contact@gmail.com"
SENDER_NAME = "Dealkly Alerts"
WATCHLIST_SETUP_URL = "https://dealkly.github.io/deal-alerts/watchlist-setup.html"
CONTACT_URL = "https://dealkly.github.io/deal-alerts/contact.html"


def fetch_active_gumroad_subscribers():
    """Fetch active premium subscribers and their watchlist keywords from Gumroad."""
    if not GUMROAD_ACCESS_TOKEN:
        print("Skipping Gumroad sync: GUMROAD_ACCESS_TOKEN not set.")
        return None

    active_subscribers = []
    url = "https://api.gumroad.com/v2/sales"
    params = {"access_token": GUMROAD_ACCESS_TOKEN}

    while url:
        resp = requests.get(url, params=params, timeout=30)

        if resp.status_code != 200:
            print(f"Gumroad API error: {resp.status_code} {resp.text}")
            return None

        data = resp.json()
        sales = data.get("sales", [])

        for sale in sales:
            email = sale.get("email")
            subscription_id = sale.get("subscription_id")
            cancelled = sale.get("subscription_cancelled", False)
            failed = sale.get("subscription_failed", False)

            if not email or not subscription_id or cancelled or failed:
                continue

            watchlist_keywords = extract_watchlist_keywords(sale)

            active_subscribers.append({
                "email": email,
                "keywords": watchlist_keywords
            })

        next_url = data.get("next_page_url")
        if next_url:
            url = next_url
            params = None
        else:
            break

    if not active_subscribers:
        print("No active Gumroad subscribers found.")
        return []

    return active_subscribers


def extract_watchlist_keywords(sale):
    """Extract watchlist keywords from Gumroad custom fields."""
    raw_keywords = ""

    custom_fields = sale.get("custom_fields", {})

    if isinstance(custom_fields, list):
        for field in custom_fields:
            if isinstance(field, dict):
                field_name = str(field.get("name", "")).lower()
                field_value = field.get("value", "")

                if any(key in field_name for key in ["watchlist", "keyword", "item", "my items"]):
                    raw_keywords = field_value
                    break

    elif isinstance(custom_fields, dict):
        for key, value in custom_fields.items():
            key_lower = str(key).lower()

            if any(k in key_lower for k in ["watchlist", "keyword", "item", "my items"]):
                raw_keywords = value
                break

    if not raw_keywords:
        for alt_key in ["watchlist", "watchlist_keywords", "keywords", "my_items"]:
            if sale.get(alt_key):
                raw_keywords = sale.get(alt_key)
                break

    if not raw_keywords:
        return []

    if isinstance(raw_keywords, list):
        return [str(k).strip() for k in raw_keywords if str(k).strip()]

    text = str(raw_keywords)

    parts = re.split(r"[,|\n]+", text)

    return [part.strip() for part in parts if part.strip()]


def read_json_file(path, default):
    """Read a JSON list from a file if it exists."""
    if not os.path.exists(path):
        return default

    try:
        with open(path, "r") as f:
            data = json.load(f)

            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"Warning: Could not read {path}: {e}")

    return default


def write_json_file(path, data):
    """Write a JSON list to a file."""
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def read_existing_watchlist():
    return read_json_file(WATCHLIST_FILE, [])


def read_sent_setup_emails():
    return read_json_file(SETUP_EMAIL_FILE, [])


def write_paid_subscribers(subscribers):
    emails = [sub["email"] for sub in subscribers]

    write_json_file(PAID_FILE, emails)
    print(f"Updated {PAID_FILE}: {len(emails)} emails")


def write_watchlist(subscribers):
    existing = read_existing_watchlist()

    current_emails = {sub["email"] for sub in subscribers}
    merged = [entry for entry in existing if entry.get("email") not in current_emails]

    for sub in subscribers:
        keywords = sub.get("keywords", [])

        if not keywords:
            continue

        merged.append({
            "email": sub["email"],
            "keywords": keywords
        })

    write_json_file(WATCHLIST_FILE, merged)
    print(f"Updated {WATCHLIST_FILE}: {len(merged)} watchlist entries")


def send_watchlist_setup_email(email):
    """Send a one-time email asking a premium subscriber to configure their watchlist."""
    if not GMAIL_APP_PASSWORD:
        print("Skipping premium setup email: GMAIL_APP_PASSWORD not set.")
        return False

    subject = "Dealkly Premium – Activate Your Watchlist"

    html_body = f"""
    <div style="background:#F5EFE6;padding:30px;font-family:Arial,sans-serif;">
      <div style="max-width:520px;margin:0 auto;background:#FFFFFF;border-radius:14px;overflow:hidden;border:1px solid #E5E7EB;">
        <div style="background:linear-gradient(135deg,#92400E,#78350F);padding:24px;text-align:center;">
          <img src="https://dealkly.github.io/deal-alerts/logo_white.png" alt="Dealkly" style="height:34px;width:auto;display:block;margin:0 auto;" />
        </div>
        <div style="padding:24px;">
          <h2 style="color:#1D2023;font-size:20px;margin:0 0 10px;">Premium is Active</h2>
          <p style="color:#4B5563;font-size:14px;line-height:1.5;margin:0 0 16px;">
            Set up a personalized watchlist so Dealkly can begin tracking the items that matter.
          </p>
          <a href="{WATCHLIST_SETUP_URL}" style="display:inline-block;background:linear-gradient(135deg,#D97706,#B45309);color:#FFFFFF;padding:12px 24px;border-radius:8px;text-decoration:none;font-weight:bold;font-size:14px;">Activate Watchlist</a>
        </div>
        <div style="background:linear-gradient(135deg,#92400E,#78350F);padding:20px;text-align:center;">
          <p style="margin:0;font-size:12px;">
            <a href="{CONTACT_URL}" style="color:#FDE68A;text-decoration:underline;">Contact</a>
          </p>
        </div>
      </div>
    </div>
    """

    text_body = (
        "Dealkly Premium is active.\n\n"
        "Set up a personalized watchlist so Dealkly can begin tracking the items that matter.\n\n"
        f"Activate Watchlist: {WATCHLIST_SETUP_URL}\n"
        f"Contact: {CONTACT_URL}\n"
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = f"{SENDER_NAME} <{SENDER}>"
    msg["To"] = email
    msg["Subject"] = subject
    msg.attach(MIMEText(text_body, "plain"))
    msg.attach(MIMEText(html_body, "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(SENDER, GMAIL_APP_PASSWORD)
        server.send_message(msg)

    print(f"Premium setup email sent to {email}")
    return True


def send_missing_watchlist_setup_emails(subscribers):
    """Send setup emails to active premium subscribers who have not yet configured a watchlist."""
    if not subscribers:
        print("No active premium subscribers found. Skipping premium setup emails.")
        return

    if not GMAIL_APP_PASSWORD:
        print("Skipping premium setup emails: GMAIL_APP_PASSWORD not set.")
        return

    subscribers_without_keywords = [sub for sub in subscribers if not sub.get("keywords")]

    if not subscribers_without_keywords:
        print("All active premium subscribers already have watchlists.")
        return

    already_sent = read_sent_setup_emails()

    for sub in subscribers_without_keywords:
        email = sub["email"]

        if email in already_sent:
            continue

        try:
            sent = send_watchlist_setup_email(email)

            if sent:
                already_sent.append(email)
        except Exception as e:
            print(f"Failed to send premium setup email to {email}: {e}")

    write_json_file(SETUP_EMAIL_FILE, already_sent)
    print(f"Updated {SETUP_EMAIL_FILE}: {len(already_sent)} sent emails")


def main():
    subscribers = fetch_active_gumroad_subscribers()

    if subscribers is None:
        print("Gumroad sync skipped.")
        return

    write_paid_subscribers(subscribers)
    write_watchlist(subscribers)
    send_missing_watchlist_setup_emails(subscribers)


if __name__ == "__main__":
    main()
