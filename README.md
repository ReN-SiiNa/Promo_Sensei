# PromoSensei – Agentic Promotional Deal Assistant

PromoSensei is an AI **agent** that helps shoppers find the best promotional deals across Flipkart, Nykaa, and Puma. Product deals are scraped and embedded into a FAISS index; a Claude-powered agent then answers questions by choosing and chaining its own tools — semantic search, structured filtering, product comparison, aggregate stats, and an on-demand live re-scrape.

It runs locally with **no GPU**: the LLM is the hosted Claude API (default `claude-opus-4-8`, or any model reached through a Portkey gateway), and only a small on-device embedding model (`all-MiniLM-L6-v2`) is needed for retrieval. The UI streams the agent's reasoning and answer token-by-token.

> Originally a single-shot RAG demo (retrieve top-5 → one local Zephyr-7B call → answer), now rebuilt as a tool-using agent.

---
![Screenshot 2025-05-23 151326](https://github.com/user-attachments/assets/a04bd48b-6e81-4a46-ac55-19a9917546ca)

## 🚀 Features

* 🤖 **Agentic tool use (raw SDK, two backends)**
  A hand-written tool-use loop lets Claude decide which tools to call and in what order, looping until it can answer. Runs against either the Anthropic Messages API or a Portkey gateway; both stream, so the Streamlit UI shows the agent's reasoning, tool calls, and answer live.

* 🧰 **Five tools over the deal catalog**
  `search_products` (semantic), `filter_deals` (min discount / price ceiling / brand), `compare_products`, `deal_stats`, and `refresh_deals` (slow live re-scrape — one site, or `source="all"` to pull the top few from all three at once).

* 🧠 **Semantic search with FAISS**
  Product metadata embedded with `sentence-transformers` and indexed with FAISS for fast vector similarity retrieval.

* 🖥️ **Local, no-GPU Streamlit UI**
  Clone and run — no large model weights to download.

Example questions:
* "Puma shoes under ₹3000 with at least 40% off"
* "What's the single biggest discount right now?"
* "Compare a face serum and a moisturiser deal"
* "Any fresh Nykaa deals?" (triggers a live scrape)

---

## 📹 Video Demo

> Watch the full walkthrough of PromoSensei in action:

<!-- 📺 [**Demo Video**](https://drive.google.com/file/d/17qUWjoa3Y_5eKlc6sRdBI7JVALnQoVtw/view?usp=sharing) -->


https://github.com/user-attachments/assets/67895deb-6ba4-4003-ac17-3a001a541728




---

## 🛠️ Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium   # only needed for scraping / the live refresh tool
```

### 2. Add your API key

```bash
cp .env.example .env      # then edit .env
```

Two backends, selected by env (see `.env.example`):

* **Direct Anthropic** (default) — set `ANTHROPIC_API_KEY` (or run `ant auth login`; the SDK picks up the profile automatically). Optionally override the model with `ANTHROPIC_MODEL`.
* **Portkey gateway** — set `PORTKEY_API_KEY` to switch on the gateway path, plus `PORTKEY_MODEL` (your gateway's model slug) and `PORTKEY_GATEWAY_URL`.

Set `PROMO_DEBUG=1` to log the resolved Portkey model + gateway on each turn.

### 3. Run the agent

The repo ships with a prebuilt `product_faiss.index` + `product_metadata.json`, so you can launch straight away:

```bash
streamlit run app.py
```

---

## 🔄 Rebuilding the deal catalog (optional)

Only needed if you want fresh data. The pipeline is a linear set of manual steps:

```bash
python scraper.py            # 1. scrape raw HTML → data/{flipkart,nykaa,puma}/
python flip_collection.py    # 2. parse each site → <site>_products.json
python nyka_collection.py
python puma_collection.py
python faiss_index_builder.py # 3. embed + build product_faiss.index + product_metadata.json
```

* Scraping uses **Playwright** (headless Chromium, self-managed browser — no chromedriver).
* `flipkart`/`nykaa` paginate via URL; `puma` scroll-loads dynamically.
* The site selectors are obfuscated CSS classes that change often — if parsing yields empty products, the selectors have gone stale.

---

## 🧱 Architecture

```
┌─ Data pipeline (offline) ──────────────┐   ┌─ Agent (online) ─────────────────────┐
│ scraper.py → *_collection.py           │   │ app.py (Streamlit, streams reasoning) │
│   → faiss_index_builder.py             │   │   → promo_agent.py  (manual tool loop)│
│   → product_faiss.index + metadata.json│──▶│      → promo_tools.py (schemas+dispatch)│
└────────────────────────────────────────┘   │         → promo_data.py (search/filter)│
                                              │         → live_scrape.py (refresh tool)│
                                              └───────────────────────────────────────┘
```

* **`promo_data.py`** — pure data layer (no LLM): loads the index, parses the messy `₹`/discount strings, and implements search/filter/compare/stats.
* **`promo_tools.py`** — Anthropic tool schemas + `run_tool` dispatch.
* **`promo_agent.py`** — the manual `while stop_reason == "tool_use"` loop over `claude-opus-4-8` with adaptive thinking, yielding events to the UI.
* **`live_scrape.py`** — bounded live re-scrape behind the `refresh_deals` tool (Playwright, imported lazily).

---

## 🤖 Model Info

* **Agent LLM**: `claude-opus-4-8` via the Anthropic API (adaptive thinking).
* **Embedding model**: `sentence-transformers/all-MiniLM-L6-v2` (runs locally).

The original local `HuggingFaceH4/zephyr-7b-alpha` (GPU-bound) has been retired; `torch`/`transformers`/`bitsandbytes` are no longer required.

---

## 🔐 Notes

* The `refresh_deals` tool uses Playwright's Chromium (install once via `python -m playwright install chromium`); it's slow, so the agent only uses it on explicit request. Live-scraped products are held in memory for the session, not written back to disk.
* The `promosensie.ipynb` notebook is the legacy GPU/Zephyr (Kaggle/Colab) implementation, kept for reference.

---

