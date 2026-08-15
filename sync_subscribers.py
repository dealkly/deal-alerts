import os
import json
import requests

GUMROAD_ACCESS_TOKEN = os.environ.get("GUMROAD_ACCESS_TOKEN", "")
FORMSPREE_API_KEY = os.environ.get("FORMSPREE_API_KEY", "")

PAID_FILE = "paid_subscribers.json"
FREE_FILE = "free_subscribers.json"


def fetch_active_gumroad_subscribers():
    """Fetch active premium subscribers from Gumroad."""
    if not GUMROAD_ACCESS_TOKEN:
        print("Skipping Gumroad sync: GUMROAD_ACCESS_TOKEN not set.")
        return None

    emails = set()
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

            if email and subscription_id and not cancelled and not failed:
                emails.add(email)

        next_url = data.get("next_page_url")
        if next_url:
            url = next_url
            params = None
        else:
            break

    if not emails:
        print("No active Gumroad subscribers found.")
        return []

    return sorted(emails)


def fetch_formspree_submissions():
    """Fetch free signup emails from Formspree."""
    if not FORMSPREE_API_KEY:
        print("Skipping Formspree sync: FORMSPREE_API_KEY not set.")
        return None

    form_id = "mwvdklly"
    url = f"https://formspree.io/api/0/forms/{form_id}/submissions"
    headers = {"Authorization": f"Bearer {FORMSPREE_API_KEY}"}

    emails = set()

    while url:
        resp = requests.get(url, headers=headers, timeout=30)

        if resp.status_code != 200:
            print(f"Formspree API error: {resp.status_code} {resp.text}")
            return None

        data = resp.json()
        submissions = data.get("submissions", [])

        for submission in submissions:
            form_data = submission.get("data", {})
            email = form_data.get("email")
            if email:
                emails.add(email)

        next_url = data.get("next_page_url") or data.get("next")
        if next_url:
            url = next_url
        else:
            break

    if not emails:
        print("No Formspree submissions found.")
        return []

    return sorted(emails)


def main():
    gumroad_emails = fetch_active_gumroad_subscribers()
    formspree_emails = fetch_formspree_submissions()

    if gumroad_emails is not None:
        with open(PAID_FILE, "w") as f:
            json.dump(gumroad_emails, f, indent=2)
        print(f"Updated {PAID_FILE}: {len(gumroad_emails)} emails")

    if formspree_emails is not None:
        with open(FREE_FILE, "w") as f:
            json.dump(formspree_emails, f, indent=2)
        print(f"Updated {FREE_FILE}: {len(formspree_emails)} emails")


if __name__ == "__main__":
    main()
