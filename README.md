# PromoSensei – AI-Powered Promotional Offer Assistant

PromoSensei is an end-to-end Retrieval-Augmented Generation (RAG) system that scrapes promotions and discounts from e-commerce websites, indexes them using FAISS with semantic vector embeddings, and allows users to query them via natural language using a powerful open-source LLM (`Zephyr-7b-alpha`).

---

## 🚀 Features

* 🕷️ **Web Scraping with Selenium + BeautifulSoup**
  Dynamically scrapes promotional offers from static & JavaScript-heavy websites.

* 🧠 **Semantic Search with FAISS**
  Product metadata is embedded using `sentence-transformers` and indexed with FAISS for fast vector similarity retrieval.

* 💬 **LLM-Powered Responses**
  Uses `Zephyr-7b-alpha` (open-source language model from Hugging Face) to generate natural language answers for queries like:

  * “Any flat 50% off deals today?”
  * “What are the top loyalty cashback offers on Nykaa?”
  * “Summarize the latest fashion discounts from Adidas”

* 🖥️ **Streamlit UI (Optional)**
  Lightweight, interactive front-end to query offers.

---

## 📹 Video Demo

> Watch the full walkthrough of PromoSensei in action:

📺 [**Demo Video**](https://drive.google.com/file/d/17qUWjoa3Y_5eKlc6sRdBI7JVALnQoVtw/view?usp=sharing)

> Replace `your-demo-video-id` with your actual demo video path hosted on Google Drive, YouTube, or any public platform.

---

## 🛠️ Setup Instructions

### ✅ 1. Environment Setup

Install dependencies:

```bash
pip install -r requirements.txt
```

> If using Jupyter, use `!pip install ...` in notebook cells.

---

### ✅ 2. Run Web Scraper

Start by scraping raw HTML product pages from different e-commerce websites. Run:

```bash
python scraper.py
```

This will store the HTML files in structured folders based on the source site:

```
data/flipkart/
data/nykaa/
data/puma/
```

* `flipkart` and `nykaa` use static page scraping.
* `puma` uses Selenium for dynamic page rendering.

---

### ✅ 3. Extract Structured Data

Once HTML files are stored, run the respective collection scripts to parse and convert them into structured JSON metadata:

```bash
python flipkart_collection.py
python nykaa_collection.py
python puma_collection.py
```

Each script reads HTML files from `data/<website>/` and generates a unified metadata file containing product title, brand, discount, price, and product URL.

---

### ✅ 4. Build FAISS Vector Index

Now use the processed JSON data to create a vector database using semantic embeddings.

Run:

```bash
python faiss_index_builder.py
```

This uses the `all-MiniLM-L6-v2` embedding model to encode metadata and builds:

```
product_faiss.index
product_metadata.json
```

These files are used for fast vector similarity search in the retrieval pipeline.

---


### ✅ 5. Launch Streamlit UI

```bash
streamlit run app.py
```
Make sure the following files are present:

* `/product_metadata.json`
* `/product_faiss.index`

This provides a simple web interface to ask promotional queries like:

```
What are the top loyalty cashback offers on Nykaa?
```

---

### ☁️ Cloud Execution

To run this on cloud GPU (e.g., for faster LLM inference), use the [**PromoSensei Notebook**](/promosensie.ipynb) which is preconfigured for GPU environments.

---

## 📦 Dependencies

* `selenium`, `beautifulsoup4`, `requests`
* `transformers`, `sentence-transformers`, `torch`
* `faiss-cpu`
* `streamlit`, `pyngrok`

Install them with:

```bash
pip install -r requirements.txt
```

---

## 🤖 Model Info

* **Embedding Model**: `sentence-transformers/all-MiniLM-L6-v2`
* **LLM**: `HuggingFaceH4/zephyr-7b-alpha` (loaded via Hugging Face)

> You can swap Zephyr for smaller open-source models (e.g., TinyLlama, Phi-2) if needed.

---

## 📬 Example Query

```text
User: What are the best fashion offers today?
→ AI: Here are the latest deals: Adidas is offering 40% off on select shoes, Nykaa has flat 50% cashback on beauty products, and more!
```

---

## 🔐 Notes

* Hugging Face models like Zephyr may require authentication via token.
* For demo videos, replace paths like `output/product_metadata.json` and `output/product_faiss.index` with your own test files or static samples.

---

