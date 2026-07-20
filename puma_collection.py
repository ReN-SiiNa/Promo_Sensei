import os
import json
from bs4 import BeautifulSoup

def extract_puma_product_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    product_item = soup.find('li', {'data-test-id': 'product-list-item'})
    
    if not product_item:
        return None
    
    product_data = {
        "brand": "Puma",
        "title": None,
        "product_link": None,
        "price": None,
        "original_price": None,
        "discount": None,
        "tag": None
    }
    
    # Extract product link (also the most reliable title source via aria-label)
    link_element = product_item.find('a', {'data-test-id': 'product-list-item-link'})
    if link_element and 'href' in link_element.attrs:
        product_data['product_link'] = "https://in.puma.com" + link_element['href']

    # Extract title. Puma's markup has shifted over time: older captures used
    # <h3>, current pages use <h2>. Fall back to the link's aria-label (which
    # embeds the product name) so this survives the next tag rename.
    title_element = product_item.find('h3') or product_item.find('h2')
    if title_element:
        product_data['title'] = title_element.get_text(strip=True)
    elif link_element and link_element.get('aria-label'):
        # aria-label: "2 Colors, <Name>, Discounted Price, ₹.., Regular price, ..."
        parts = [p.strip() for p in link_element['aria-label'].split(',')]
        name = next((p for p in parts if p and 'color' not in p.lower()
                     and 'price' not in p.lower() and '₹' not in p and '%' not in p), None)
        product_data['title'] = name
    
    # Extract prices
    price_element = product_item.find('span', {'data-test-id': 'sale-price'})
    if price_element:
        product_data['price'] = price_element.get_text(strip=True)
    
    original_price_element = product_item.find('span', {'data-test-id': 'price'})
    if original_price_element:
        product_data['original_price'] = original_price_element.get_text(strip=True)
    
    # Extract discount
    discount_element = product_item.find('span', {'data-test-id': 'product-badge-sale'})
    if discount_element:
        product_data['discount'] = discount_element.get_text(strip=True)
    
    # Extract promotion tag
    promotion_element = product_item.find('p', {'data-test-id': 'promotion-callout-message'})
    if promotion_element:
        product_data['tag'] = promotion_element.get_text(strip=True)
    
    return product_data

def process_puma_files(input_folder, output_file):
    all_products = []
    
    for filename in os.listdir(input_folder):
        if filename.endswith('.html'):
            filepath = os.path.join(input_folder, filename)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            product_data = extract_puma_product_data(html_content)
            if product_data:
                all_products.append(product_data)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully processed {len(all_products)} products. Output saved to {output_file}")

# Usage — guarded so importing this module (e.g. for extract_puma_product_data)
# does not re-parse and overwrite the JSON.
if __name__ == "__main__":
    input_folder = 'data/puma'
    output_file = 'puma_products.json'
    process_puma_files(input_folder, output_file)