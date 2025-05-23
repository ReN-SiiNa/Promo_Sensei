import os
import json
from bs4 import BeautifulSoup

def extract_product_data(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')
    product_wrapper = soup.find('div', class_='productWrapper')
    
    if not product_wrapper:
        return None
    
    product_data = {
        "brand": None,
        "title": None,
        "product_link": None,
        "price": None,
        "original_price": None,
        "discount": None,
        "rating": None
    }
    
    # Extract title first
    title_element = product_wrapper.find('div', class_='css-xrzmfa')
    if title_element:
        full_title = title_element.get_text(strip=True)
        product_data['title'] = full_title
        
        # Extract brand as first word of title
        if full_title:
            product_data['brand'] = full_title.split()[0]  # First word as brand
    
    # Extract product link
    link_element = product_wrapper.find('a', class_='css-qlopj4')
    if link_element and 'href' in link_element.attrs:
        product_data['product_link'] = "https://www.nykaa.com" + link_element['href']
    
    # Extract prices
    price_element = product_wrapper.find('span', class_='css-111z9ua')
    if price_element:
        product_data['price'] = price_element.get_text(strip=True)
    
    original_price_element = product_wrapper.find('span', class_='css-17x46n5')
    if original_price_element:
        original_price_text = original_price_element.get_text(strip=True)
        if '₹' in original_price_text:
            product_data['original_price'] = original_price_text.split('₹')[-1].strip()
    
    discount_element = product_wrapper.find('span', class_='css-cjd9an')
    if discount_element:
        product_data['discount'] = discount_element.get_text(strip=True)
    
    # Extract rating
    rating_wrap = product_wrapper.find('div', class_='css-wskh5y')
    if rating_wrap:
        rating_text = rating_wrap.find('span', class_='css-1qbvrhp')
        if rating_text:
            product_data['rating'] = rating_text.get_text(strip=True).strip('()')
    
    return product_data

def process_nykaa_files(input_folder, output_file):
    all_products = []
    
    for filename in os.listdir(input_folder):
        if filename.endswith('.html'):
            filepath = os.path.join(input_folder, filename)
            
            with open(filepath, 'r', encoding='utf-8') as f:
                html_content = f.read()
            
            product_data = extract_product_data(html_content)
            if product_data:
                all_products.append(product_data)
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(all_products, f, indent=2, ensure_ascii=False)
    
    print(f"Successfully processed {len(all_products)} products. Output saved to {output_file}")

# Usage
input_folder = 'data/nykaa'
output_file = 'nykaa_products.json'
process_nykaa_files(input_folder, output_file)