import requests
from bs4 import BeautifulSoup
import time
from urllib.parse import urljoin
import csv
import os
import smtplib

base_url = "http://books.toscrape.com"
current_url = base_url
page_number = 1
total_books = 0

# Create/open CSV file for writing
csv_file = open("books_catalog.csv", "w", newline="", encoding="utf-8")
csv_writer = csv.writer(csv_file)
csv_writer.writerow(["Title", "Price"])  # header row

while current_url:
    print(f"--- Page {page_number} ---")

    try:
        response = requests.get(current_url, timeout=10)
        response.encoding = 'utf-8'
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        books = soup.find_all("article", class_="product_pod")

        for book in books:
            try:
                title = book.h3.a['title']
                price = book.find("p", class_="price_color").text
                print(f"  {title} - {price}")
                # Write row to CSV
                csv_writer.writerow([title, price])
                total_books += 1
            except AttributeError:
                print("  [Skipping malformed entry]")
                continue

        next_button = soup.find("li", class_="next")
        if next_button:
            current_url = urljoin(response.url, next_button.a['href'])
            page_number += 1
            time.sleep(1)
        else:
            current_url = None

    except requests.exceptions.RequestException as e:
        print(f"  Network error: {e}")
        print("  Retrying in 5 seconds...")
        time.sleep(5)
        continue

csv_file.close()
print(f"\nDone. {total_books} books saved to books_catalog.csv")
# Phase 4: Act (Email Notification)
sender_email = "meshsami321@gmail.com"
receiver_email = "meshsami321@gmail.com"

# Retrieve the secure key from the GitHub memory vault
app_password = os.environ.get("GMAIL_APP_PASSWORD") 

subject = "Automation Engine Alert"
body = "The data harvesting pipeline has executed successfully and updated the books catalog."
email_message = f"Subject: {subject}\n\n{body}"

try:
    server = smtplib.SMTP("smtp.gmail.com", 587)
    server.starttls()
    server.login(sender_email, app_password)
    server.sendmail(sender_email, receiver_email, email_message)
    server.quit()
    print("Alert routed successfully.")
except Exception as error_signal:
    print(f"Alert routing failed: {error_signal}")