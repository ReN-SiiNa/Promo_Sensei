import json
import faiss  # This is the actual library
import numpy as np
from sentence_transformers import SentenceTransformer

# Load JSON data from files
def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

flipkart_products = load_json("flipkart_products.json")
nykaa_products = load_json("nykaa_products.json")
puma_products = load_json("puma_products.json")

# Normalize Nykaa products by adding default tag
for product in nykaa_products:
    if "tag" not in product or not product["tag"]:
        product["tag"] = "bestseller"

# Merge all products into one list
all_products = flipkart_products + nykaa_products + puma_products

# Prepare text data for embedding
def product_to_text(prod):
    brand = prod.get("brand", "")
    title = prod.get("title", "")
    price = str(prod.get("price", ""))
    original_price = str(prod.get("original_price", ""))
    discount = str(prod.get("discount", ""))
    tag = prod.get("tag", "")
    
    combined_text = f"Brand: {brand} Title: {title} Price: {price} Original Price: {original_price} Discount: {discount} Tag: {tag}"
    return combined_text

texts = [product_to_text(prod) for prod in all_products]

# Load embedding model
model = SentenceTransformer('all-MiniLM-L6-v2')

# Create embeddings (numpy array)
embeddings = model.encode(texts, show_progress_bar=True, convert_to_numpy=True)

# Normalize embeddings (optional, for cosine similarity)
faiss.normalize_L2(embeddings)

# Create FAISS index (IndexFlatIP for cosine similarity)
dimension = embeddings.shape[1]
index = faiss.IndexFlatIP(dimension)

# Add vectors to the index
index.add(embeddings)

# Save the index and metadata
faiss.write_index(index, "product_faiss.index")

with open("product_metadata.json", "w", encoding="utf-8") as f:
    json.dump(all_products, f, indent=2)

print(f"Indexed {len(all_products)} products into FAISS.")
