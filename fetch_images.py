import re
import urllib.request

PRODUCTS = {
    "microsoft365": "https://o365itpros.gumroad.com/l/O365IT",
    "ai_video_studio": "https://kevinvandermarliere.gumroad.com/l/Aivideostudio",
    "gsonic_immersive": "https://oca2026.gumroad.com/l/ntcuxn",
    "audio_consultation": "https://tudorhg.gumroad.com/l/gindil",
    "gsonic_evo32": "https://oca2026.gumroad.com/l/evo32",
    "ross_mills": "https://rossmillsrant.gumroad.com/l/bldhl",
    "simpligen": "https://simpligen.gumroad.com/l/simpligen",
    "hacking_with_swift": "https://twostraws.gumroad.com/l/hws-subscription",
    "stellarizer": "https://s1gnsofl1fe.gumroad.com/l/stellarizer",
    "catpin": "https://alexsokol.gumroad.com/l/catpin",
}


def fetch_og_image(url):
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0 Safari/537.36"
            },
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="ignore")

        match = re.search(
            r'property=["\']og:image["\']\s+content=["\']([^"\']+)["\']',
            html,
            re.IGNORECASE,
        )
        if not match:
            match = re.search(
                r'content=["\']([^"\']+)["\']\s+property=["\']og:image["\']',
                html,
                re.IGNORECASE,
            )
        if match:
            return match.group(1)
    except Exception as e:
        return f"ERROR: {e}"

    return "NOT FOUND"


if __name__ == "__main__":
    for name, url in PRODUCTS.items():
        image_url = fetch_og_image(url)
        print(f"{name}:")
        print(f"  page: {url}")
        print(f"  image: {image_url}")
        print()
