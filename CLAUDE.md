# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

PromoSensei is an **agentic** deal assistant for e-commerce promotions. Scraped product deals from Flipkart, Nykaa, and Puma are embedded into a FAISS index; a Claude-powered agent (`claude-opus-4-8`) answers shopper questions by choosing and chaining its own tools — semantic search, structured filtering, comparison, aggregate stats, and an on-demand live re-scrape. It runs locally with no GPU: the LLM is the hosted Claude API, and only the small `all-MiniLM-L6-v2` embedder runs on-device.

It was originally a single-shot RAG app (retrieve top-5 → one local Zephyr-7B call → answer). That has been replaced by the agent loop below; the old scrape/parse/index pipeline is retained as the data source.

## Two layers

**1. Data pipeline (offline, file-based)** — unchanged from the original design; produces the committed `product_faiss.index` + `product_metadata.json`:

1. **Scrape** (`scraper.py`) — one headless Playwright Chromium scrapes all three sites → raw HTML fragments in `data/<site>/`.
2. **Parse** (`flip_collection.py`, `nyka_collection.py`, `puma_collection.py`) — per-site BeautifulSoup selectors → `<site>_products.json`. Selectors are obfuscated CSS classes (`a.WKTcLC`, `css-xrzmfa`) that go stale often — parse breakage is almost always stale selectors, not logic.
3. **Index** (`faiss_index_builder.py`) — merges the JSONs, serializes each product to one string, embeds with `all-MiniLM-L6-v2`, L2-normalizes, builds a cosine `IndexFlatIP`. FAISS row `i` ↔ `metadata[i]`.

**2. Agent (online, what the UI runs)** — new modules, layered so the LLM is isolated from the data logic:

- **`promo_data.py`** — pure data layer, no LLM. Loads the index+metadata, parses the messy scraped values, and implements `search_products` / `filter_deals` / `compare_products` / `deal_stats` / `add_products`. Testable standalone.
- **`promo_tools.py`** — Anthropic tool schemas (`TOOLS`) + `run_tool(name, input)` dispatch to `promo_data`. Errors are returned as `{"error": ...}` payloads, never raised, so the agent can recover.
- **`promo_agent.py`** — the **manual** tool-use loop, written out rather than using an SDK tool runner. `run_agent()` is a generator yielding `thinking` / `tool_use` / `tool_result` / `text` / `answer` / `error` events so the UI can stream reasoning. **Two backends, selected by env:**
  - Default: Anthropic Messages API (`claude-opus-4-8`, adaptive thinking) via `_run_anthropic`.
  - Portkey: if `PORTKEY_API_KEY` is set, the `portkey_ai` SDK against the Portkey gateway using the OpenAI chat.completions + function-calling shape (`_run_portkey`, model from `PORTKEY_MODEL`). Both share `promo_tools.run_tool` dispatch and emit the same events, so `app.py` is backend-agnostic. `promo_tools.openai_tools()` converts the tool schemas to OpenAI function format for this path.
- **`live_scrape.py`** — bounded per-source re-scrape behind the `refresh_deals` tool. Reuses the pipeline's parse functions, embeds results, and appends them to the in-memory catalog via `promo_data.add_products` (not persisted). Playwright is imported lazily — only needed if this tool runs.
- **`app.py`** — Streamlit chat UI that consumes `run_agent`'s event stream and renders reasoning + each tool call/result in expanders.

## Data contract & value formats

Products flow as dicts with canonical fields `brand`, `title`, `price`, `original_price`, `discount`, `tag`, `product_link`. `promo_data.clean_product` guarantees every canonical field is present (backfills missing `tag` to `"—"`), so nothing downstream can `KeyError` — this fixes a real bug in the old `app.py`, which read `doc['tag']` directly and crashed on tag-less products.

The scraped strings are messy — the parsers in `promo_data.py` handle all of it:
- **Prices**: `"₹2,289"`, `"₹1100"`, or bare `"2199"` → `parse_price` strips to a float.
- **Discounts**: three formats coexist — `"61% off"`, `"50% Off"`, and Puma's `"-50%"` → `parse_discount` regexes out the integer percent.
- ~25% of products have a null `tag`; a handful have null `discount`.
- The **₹ symbol breaks the default Windows console encoding** (cp1252) — set `PYTHONIOENCODING=utf-8` when printing product data from a terminal.

## Commands

```bash
pip install -r requirements.txt          # setup
cp .env.example .env                      # add ANTHROPIC_API_KEY (or use `ant auth login`)

streamlit run app.py                      # run the agent UI (uses committed index)

# Rebuild the data pipeline only if you want fresh data:
python scraper.py                         # scrape → data/<site>/*.html
python flip_collection.py                 # parse (note: flip_, not flipkart_)
python nyka_collection.py
python puma_collection.py
python faiss_index_builder.py             # build product_faiss.index + product_metadata.json
```

The committed index/metadata mean `app.py` runs out of the box — no scrape needed. There are no tests or linters.

## Gotchas

- **Credentials**: default path needs `ANTHROPIC_API_KEY` (env or `.env`) or an `ant auth login` profile. To route through Portkey instead, set `PORTKEY_API_KEY` + `PORTKEY_MODEL` (+ `PORTKEY_GATEWAY_URL` for a self-hosted gateway). See `.env.example`. No key is hardcoded.
- **`refresh_deals` needs a browser**: live scraping uses Playwright's own Chromium — install it once with `python -m playwright install chromium` (no system Chrome/chromedriver needed). It's slow (~20-60s) and the agent is prompted to use it only when the user explicitly wants fresh data. Failures return an `{"error": ...}` dict rather than crashing.
- **In-memory only**: products added by `refresh_deals` live for the process lifetime; they are not written back to `product_metadata.json` / the index file.
- **Model pin**: `promo_agent.MODEL = "claude-opus-4-8"`, adaptive thinking (`{"type": "adaptive"}`), `MAX_TURNS = 8` caps the tool loop.
- **Legacy files**: `promosensie.ipynb` is the old GPU/Zephyr notebook (Kaggle/Colab) and still references `slack_bolt`/`pyngrok`; those integrations never existed in the `.py` files. `torch`/`transformers`/`bitsandbytes` are no longer dependencies — the local 7B model was removed.
- **README** still documents the original RAG flow; the agent architecture above is the current one.
