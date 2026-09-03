import os
import json
import re
import requests

GUMROAD_ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "")

PAID_FILE = "paid_subscribers.json"
WATCHLIST_FILE = "watchlist.json"


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


def read_existing_watchlist():
    """Read the existing watchlist file if it exists."""
    if not os.path.exists(WATCHLIST_FILE):
        return []

    try:
        with open(WATCHLIST_FILE, "r") as f:
            data = json.load(f)

            if isinstance(data, list):
                return data
    except Exception as e:
        print(f"Warning: Could not read {WATCHLIST_FILE}: {e}")

    return []


def write_paid_subscribers(subscribers):
    emails = [sub["email"] for sub in subscribers]

    with open(PAID_FILE, "w") as f:
        json.dump(emails, f, indent=2)

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

    with open(WATCHLIST_FILE, "w") as f:
        json.dump(merged, f, indent=2)

    print(f"Updated {WATCHLIST_FILE}: {len(merged)} watchlist entries")


def main():
    subscribers = fetch_active_gumroad_subscribers()

    if subscribers is None:
        print("Gumroad sync skipped.")
        return

    write_paid_subscribers(subscribers)
    write_watchlist(subscribers)


if __name__ == "__main__":
    main()
