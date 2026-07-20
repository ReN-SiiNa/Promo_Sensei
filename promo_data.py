"""Data layer for PromoSensei.

Loads the FAISS index + product metadata and exposes pure-Python helpers
(semantic search, structured filtering, comparison, stats) that the agent's
tools call. Deliberately has no LLM dependency so it can be tested in isolation.

The scraped data is messy — prices look like "₹2,289" or "₹1100", discounts
come in three flavours ("61% off", "50% Off", Puma's "-50%"), and ~25% of
products have no `tag`. The parsers below normalise all of that.
"""

import json
import re
from functools import lru_cache

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

# --------------------------------------------------------------------------
# Paths (repo-root relative, not the old hardcoded /kaggle/input paths)
# --------------------------------------------------------------------------
INDEX_PATH = "product_faiss.index"
METADATA_PATH = "product_metadata.json"
EMBED_MODEL = "all-MiniLM-L6-v2"

# Canonical fields the agent reasons over.
CANONICAL_FIELDS = ("brand", "title", "price", "original_price", "discount", "tag", "product_link")


# --------------------------------------------------------------------------
# Value parsers — turn the scraped strings into numbers
# --------------------------------------------------------------------------
def parse_price(value):
    """'₹2,289' | '₹1100' | '2199' | None  ->  float rupees, or None."""
    if value is None:
        return None
    digits = re.sub(r"[^\d.]", "", str(value))
    if not digits:
        return None
    try:
        return float(digits)
    except ValueError:
        return None


def parse_discount(value):
    """'61% off' | '50% Off' | '-50%' | None  ->  int percent, or None."""
    if value is None:
        return None
    match = re.search(r"(\d+)\s*%", str(value))
    return int(match.group(1)) if match else None


def clean_product(prod):
    """Return a product dict with every canonical field present (never KeyErrors
    downstream) plus parsed numeric helpers."""
    out = {field: prod.get(field) for field in CANONICAL_FIELDS}
    # The index builder backfills Nykaa tags to "bestseller"; anything still
    # missing gets a neutral placeholder so the prompt never sees None.
    if not out.get("tag"):
        out["tag"] = "—"
    out["_price"] = parse_price(prod.get("price"))
    out["_discount"] = parse_discount(prod.get("discount"))
    return out


# --------------------------------------------------------------------------
# Lazy singletons — model + index load once per process
# --------------------------------------------------------------------------
@lru_cache(maxsize=1)
def _embedder():
    return SentenceTransformer(EMBED_MODEL)


@lru_cache(maxsize=1)
def _load():
    index = faiss.read_index(INDEX_PATH)
    with open(METADATA_PATH, "r", encoding="utf-8") as f:
        raw = json.load(f)
    metadata = [clean_product(p) for p in raw]
    return index, metadata


def all_products():
    return _load()[1]


def catalog_size():
    return len(all_products())


# --------------------------------------------------------------------------
# Tool operations
# --------------------------------------------------------------------------
def search_products(query, top_k=5):
    """Semantic search over the FAISS index. Returns the top_k product dicts."""
    index, metadata = _load()
    top_k = max(1, min(int(top_k), 20))
    emb = _embedder().encode([query], convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(emb)
    _scores, ids = index.search(emb, top_k)
    return [metadata[i] for i in ids[0] if 0 <= i < len(metadata)]


def filter_deals(min_discount=None, max_price=None, min_price=None,
                 brand=None, limit=10):
    """Structured (non-semantic) filter over the whole catalog, sorted by
    discount descending. Every criterion is optional."""
    results = []
    brand_q = brand.lower().strip() if brand else None
    for p in all_products():
        if min_discount is not None and (p["_discount"] is None or p["_discount"] < min_discount):
            continue
        if max_price is not None and (p["_price"] is None or p["_price"] > max_price):
            continue
        if min_price is not None and (p["_price"] is None or p["_price"] < min_price):
            continue
        if brand_q and brand_q not in (p["brand"] or "").lower():
            continue
        results.append(p)
    results.sort(key=lambda p: (p["_discount"] is None, -(p["_discount"] or 0)))
    return results[: max(1, min(int(limit), 25))]


def deal_stats(brand=None):
    """Aggregate stats across the catalog (optionally scoped to one brand):
    count, best discount, average discount, cheapest deal."""
    pool = all_products()
    if brand:
        bq = brand.lower().strip()
        pool = [p for p in pool if bq in (p["brand"] or "").lower()]

    discounts = [p["_discount"] for p in pool if p["_discount"] is not None]
    priced = [p for p in pool if p["_price"] is not None]
    top = max(pool, key=lambda p: p["_discount"] or -1, default=None)
    cheapest = min(priced, key=lambda p: p["_price"], default=None)

    return {
        "scope": brand or "all brands",
        "product_count": len(pool),
        "max_discount_pct": max(discounts) if discounts else None,
        "avg_discount_pct": round(sum(discounts) / len(discounts), 1) if discounts else None,
        "top_deal": _summarize(top) if top else None,
        "cheapest": _summarize(cheapest) if cheapest else None,
    }


def compare_products(titles):
    """Find catalog products whose title best matches each requested title
    (case-insensitive substring, falling back to semantic search) and return
    them side by side for the agent to reason over."""
    out = []
    for wanted in titles:
        wq = wanted.lower().strip()
        match = next((p for p in all_products() if wq in (p["title"] or "").lower()), None)
        if match is None:
            hits = search_products(wanted, top_k=1)
            match = hits[0] if hits else None
        if match:
            out.append(_summarize(match))
    return out


def add_products(raw_products):
    """Embed and append freshly scraped products to the in-memory FAISS index
    and metadata list (used by the live refresh_deals tool). Returns the number
    actually added. Not persisted to disk — lives for the process lifetime."""
    index, metadata = _load()
    cleaned = [clean_product(p) for p in raw_products if p and p.get("title")]
    if not cleaned:
        return 0
    texts = [
        f"Brand: {p['brand']} Title: {p['title']} Price: {p['price']} "
        f"Discount: {p['discount']} Tag: {p['tag']}"
        for p in cleaned
    ]
    emb = _embedder().encode(texts, convert_to_numpy=True).astype("float32")
    faiss.normalize_L2(emb)
    index.add(emb)
    metadata.extend(cleaned)
    return len(cleaned)


def _summarize(p):
    """Compact, JSON-friendly view used in tool results."""
    return {
        "brand": p.get("brand"),
        "title": p.get("title"),
        "price": p.get("price"),
        "original_price": p.get("original_price"),
        "discount": p.get("discount"),
        "tag": p.get("tag"),
        "link": p.get("product_link"),
    }
