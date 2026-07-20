import os
from bs4 import BeautifulSoup
import json

# Folder where your product HTML files are saved
HTML_FOLDER = "data/flipkart"

def _first_text(soup, selectors):
    """Return the stripped text of the first selector that matches, else None.
    Flipkart's obfuscated classes rotate, so each field lists current selectors
    first with older ones as fallbacks (keeps old data/flipkart/*.html parsing)."""
    for sel in selectors:
        node = soup.select_one(sel)
        if node and node.text.strip():
            return node.text.strip()
    return None


def parse_product_html(html_content):
    soup = BeautifulSoup(html_content, "html.parser")

    # Title: the anchor's `title` attr holds the full (untruncated) name.
    title = None
    for sel in ("a.atJtCj", "a.WKTcLC"):
        node = soup.select_one(sel)
        if node:
            title = (node.get("title") or node.text).strip() or None
            if title:
                break

    brand = _first_text(soup, ["div.Fo1I0b", "div.syl9yP"])

    try:
        link_node = soup.select_one("a.CIaYa1") or soup.select_one("a.atJtCj") \
            or soup.select_one("a.WKTcLC")
        product_link = "https://www.flipkart.com" + link_node["href"]
    except:
        product_link = None

    price = _first_text(soup, ["div.hZ3P6w", "div.Nx9bqj"])
    original_price = _first_text(soup, ["div.kRYCnD", "div.yRaY8j"])
    discount = _first_text(soup, ["div.HQe8jr span", "div.UkUFwK span"])
    delivery = _first_text(soup, ["div.yiggsN"])
    tag = _first_text(soup, ["div.O5Fpg8"])

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
