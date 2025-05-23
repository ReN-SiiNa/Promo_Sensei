import os
from bs4 import BeautifulSoup
import json

# Folder where your product HTML files are saved
HTML_FOLDER = "data/flipkart"

def parse_product_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    # Extract fields safely (try-except or conditional checks)
    try:
        title = soup.select_one("a.WKTcLC").text.strip()
    except:
        title = None

    try:
        brand = soup.select_one("div.syl9yP").text.strip()
    except:
        brand = None

    try:
        product_link = soup.select_one("a.WKTcLC")["href"]
        # Flipkart links are relative, add base URL
        product_link = "https://www.flipkart.com" + product_link
    except:
        product_link = None

    try:
        price = soup.select_one("div.Nx9bqj").text.strip()
    except:
        price = None

    try:
        original_price = soup.select_one("div.yRaY8j").text.strip()
    except:
        original_price = None

    try:
        discount = soup.select_one("div.UkUFwK span").text.strip()
    except:
        discount = None

    try:
        delivery = soup.select_one("div.yiggsN").text.strip()
    except:
        delivery = None

    try:
        tag = soup.select_one("div.O5Fpg8").text.strip()
    except:
        tag = None

    return {
        "title": title,
        "brand": brand,
        "product_link": product_link,
        "price": price,
        "original_price": original_price,
        "discount": discount,
        "delivery": delivery,
        "tag": tag,
    }

def main():
    all_products = []

    for filename in os.listdir(HTML_FOLDER):
        if not filename.endswith(".html"):
            continue

        filepath = os.path.join(HTML_FOLDER, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            html = f.read()

        product_data = parse_product_html(html)
        all_products.append(product_data)

    # Save all extracted products into a JSON file for later use
    with open("flipkart_products.json", "w", encoding="utf-8") as outfile:
        json.dump(all_products, outfile, ensure_ascii=False, indent=4)

    print(f"Extracted {len(all_products)} products and saved to flipkart_products.json")

if __name__ == "__main__":
    main()
