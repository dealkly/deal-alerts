best_deal = {}
    for _, row in filtered.iterrows():
        url = row.get("link_today", row.get("link_yest", ""))
        if not url:
            continue
        drop_val = -row["drop"] if row["drop"] < 0 else row["drop"]
        percent = round((drop_val / row["price_yest"]) * 100)
        
        # 1. Pull product image URL safely
        image_url = row.get("image_today", row.get("image", row.get("image_url", row.get("img", ""))))
        
        # 2. Clean and validate the URL to prevent broken images in the email
        clean_img = str(image_url).strip() if pd.notna(image_url) else ""
        if clean_img.lower() in ["nan", "none"]:
            clean_img = ""
        
        # Fix missing 'https:' schema (common with web scrapers)
        if clean_img.startswith("//"):
            clean_img = "https:" + clean_img
        # If it's not empty and still doesn't start with http, it's invalid. Hide it.
        elif clean_img and not clean_img.startswith("http"):
            clean_img = ""

        if url not in best_deal or percent > best_deal[url]["percent"]:
            best_deal[url] = {
                "title": str(row["title"]).strip(),
                "was": float(row["price_yest"]),
                "now": float(row["price_today"]),
                "save": float(drop_val),
                "percent": int(percent),
                "link": str(url).strip(),
                "image": clean_img  # Use the cleaned image URL
            }
