"""Bounded, on-demand live re-scrape for the agent's refresh_deals tool.

Reuses the same site selectors as the original scraper.py / *_collection.py
scripts, but scoped down to a single source and a small item cap so it can run
interactively (a few seconds to ~a minute) instead of the full 20-page crawl.
Freshly scraped products are embedded and appended to the in-memory catalog via
promo_data.add_products.

Uses Playwright (headless Chromium). Playwright manages its own browser binary,
so no system Chrome / chromedriver is required — but the browser must be
installed once with `python -m playwright install chromium`. Playwright is
imported lazily, so it is only needed when this tool actually runs.
"""

import promo_data as data

MAX_CAP = 40

# CSS selector for the product nodes on each source's listing page.
_LISTING = {
    "flipkart": (
        "https://www.flipkart.com/search?q=sale&sort=relevance",
        "div[data-id]",
    ),
    "nykaa": (
        "https://www.nykaa.com/bestsellers/c/15752?sort=discount",
        "div#product-list-wrap > div.productWrapper",
    ),
    "puma": (
        "https://in.puma.com/in/en/puma-sale-collection?sort=Discount-high-to-low",
        "ul#product-list-items > li[data-test-id='product-list-item']",
    ),
}


def refresh_deals(source, max_items=20):
    """Scrape `source` and ingest into the catalog, returning a summary dict.

    `source` is flipkart|nykaa|puma, or "all" to scrape every site (top
    `max_items` from each) in one call. Returns an {"error": ...} dict on
    failure so the agent can report it gracefully rather than crashing."""
    if source == "all":
        return refresh_all(max_items)
    max_items = max(1, min(int(max_items), MAX_CAP))
    if source not in _LISTING:
        return {"error": f"unknown source: {source}"}
    try:
        products = _scrape(source, max_items)
    except Exception as exc:
        msg = str(exc)
        # A hung navigation / no-response timeout on a source almost always
        # means its edge is bot-blocking us (e.g. Nykaa WAF returns 403 / stalls
        # the connection). Say so plainly instead of blaming a missing browser.
        blocked = ("Timeout" in type(exc).__name__ or "403" in msg
                   or any(m in msg for m in ("ERR_HTTP2", "ERR_CONNECTION_RESET",
                                             "ERR_CONNECTION_CLOSED", "ERR_CONNECTION_REFUSED",
                                             "ERR_NETWORK_CHANGED", "net::ERR")))
        if blocked:
            hint = (f"{source} appears to be blocking automated requests "
                    "(bot protection). Try another source or the committed catalog.")
        else:
            hint = "Run `python -m playwright install chromium` if the browser is missing."
        return {
            "error": f"live scrape failed ({type(exc).__name__}: {msg})",
            "hint": hint,
        }

    added = data.add_products(products)
    return {
        "source": source,
        "scraped": len(products),
        "added_to_catalog": added,
        "new_catalog_size": data.catalog_size(),
        "sample": [
            {"brand": p.get("brand"), "title": p.get("title"),
             "price": p.get("price"), "discount": p.get("discount")}
            for p in products[:5]
        ],
    }


def refresh_all(per_site=5):
    """Scrape the top `per_site` (default 5) deals from every source and ingest
    them. Each site is scraped independently so one being blocked doesn't sink
    the others — its failure is captured in the per-source summary instead."""
    per_site = max(1, min(int(per_site), MAX_CAP))
    per_source = {}
    total_scraped = 0
    total_added = 0
    for src in _LISTING:
        res = refresh_deals(src, max_items=per_site)
        per_source[src] = res
        if "error" not in res:
            total_scraped += res.get("scraped", 0)
            total_added += res.get("added_to_catalog", 0)
    return {
        "source": "all",
        "per_site": per_site,
        "total_scraped": total_scraped,
        "total_added_to_catalog": total_added,
        "new_catalog_size": data.catalog_size(),
        "by_source": per_source,
    }


def _scrape(source, max_items):
    from playwright.sync_api import sync_playwright

    from flip_collection import parse_product_html
    from nyka_collection import extract_product_data
    from puma_collection import extract_puma_product_data

    url, selector = _LISTING[source]
    parser = {
        "flipkart": parse_product_html,
        "nykaa": extract_product_data,
        "puma": extract_puma_product_data,
    }[source]

    products = []
    with sync_playwright() as p:
        # Nykaa's WAF blocks bundled headless Chromium (403 / connection reset).
        # Real Chrome + disabling the AutomationControlled flag gets a clean 200;
        # --disable-http2 also sidesteps ERR_HTTP2_PROTOCOL_ERROR. Fall back to
        # bundled chromium if system Chrome isn't installed.
        launch_args = ["--disable-http2", "--disable-blink-features=AutomationControlled"]
        try:
            browser = p.chromium.launch(channel="chrome", headless=True, args=launch_args)
        except Exception:
            browser = p.chromium.launch(headless=True, args=launch_args)
        context = browser.new_context(
            viewport={"width": 1400, "height": 1000},
            locale="en-IN",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36"
            ),
            extra_http_headers={
                "Accept-Language": "en-IN,en;q=0.9",
                "Accept": ("text/html,application/xhtml+xml,application/xml;q=0.9,"
                           "image/webp,*/*;q=0.8"),
            },
        )
        page = context.new_page()
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_selector(selector, timeout=15000)
            nodes = page.query_selector_all(selector)[:max_items]
            for node in nodes:
                html = node.evaluate("el => el.outerHTML")
                parsed = parser(html)
                # flipkart's parser always returns a dict; nykaa/puma may None.
                if parsed:
                    products.append(parsed)
        finally:
            browser.close()

    # Fail loudly if selectors went stale (all-None parses) — the #1 breakage.
    if products and all(not p.get("title") for p in products):
        raise RuntimeError(f"{source}: scraped {len(products)} nodes but parsed no titles "
                           "(site selectors likely changed)")
    return products
