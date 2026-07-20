"""Offline scraper — captures raw per-product HTML fragments for the pipeline.

Scrapes all three sources with one headless Chromium (Playwright) and writes
the raw outerHTML of each product node into data/<site>/*.html, which the
*_collection.py parsers then turn into JSON.

Playwright manages its own browser; install it once with:
    python -m playwright install chromium

Flipkart / Nykaa paginate via URL; Puma scroll-loads and stops after
MAX_SAME_SCROLLS scrolls yield no new product IDs.
"""

import os
import time

from playwright.sync_api import sync_playwright

MAX_PAGES = 20
SCROLL_PAUSE = 2.0
MAX_SAME_SCROLLS = 5


def _save_nodes(page, selector, folder, prefix, counter_start=0):
    """Write outerHTML of every node matching `selector` into folder. Returns
    the next counter value."""
    os.makedirs(folder, exist_ok=True)
    count = counter_start
    for node in page.query_selector_all(selector):
        html = node.evaluate("el => el.outerHTML")
        with open(f"{folder}/{prefix}_{count}.html", "w", encoding="utf-8") as f:
            f.write(html)
        count += 1
    return count


def scrape_flipkart(page):
    selector = "div[data-id]"
    count = 0
    for i in range(1, MAX_PAGES):
        url = f"https://www.flipkart.com/search?q=sale&sort=relevance&page={i}"
        print(f"Loading Flipkart page {i}...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector(selector, timeout=10000)
        except Exception as e:
            print(f"Timeout on Flipkart page {i}: {e}")
            continue
        count = _save_nodes(page, selector, "data/flipkart", "sale", count)
        print(f"  {count} Flipkart items saved so far")


def scrape_nykaa(page):
    selector = "div#product-list-wrap > div.productWrapper"
    count = 0
    for i in range(1, MAX_PAGES):
        url = f"https://www.nykaa.com/bestsellers/c/15752?page_no={i}&sort=discount"
        print(f"Loading Nykaa page {i}...")
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        try:
            page.wait_for_selector(selector, timeout=10000)
        except Exception as e:
            print(f"Timeout on Nykaa page {i}: {e}")
            continue
        count = _save_nodes(page, selector, "data/nykaa", "bestsellers", count)
        print(f"  {count} Nykaa items saved so far")


def scrape_puma(page):
    """Scroll-load the Puma sale page, saving each new product node once."""
    selector = "ul#product-list-items > li[data-test-id='product-list-item']"
    os.makedirs("data/puma", exist_ok=True)
    page.goto("https://in.puma.com/in/en/puma-sale-collection?sort=Discount-high-to-low",
              wait_until="domcontentloaded", timeout=30000)
    page.wait_for_selector(selector, timeout=15000)

    seen_ids = set()
    file_count = 0
    same_count = 0
    print("Starting Puma scroll and scrape...")
    while same_count < MAX_SAME_SCROLLS:
        page.evaluate("window.scrollBy(0, 1000)")
        time.sleep(SCROLL_PAUSE)

        new_found = 0
        for node in page.query_selector_all(selector):
            pid = node.get_attribute("data-product-id")
            if pid and pid not in seen_ids:
                seen_ids.add(pid)
                html = node.evaluate("el => el.outerHTML")
                with open(f"data/puma/product_{file_count}.html", "w", encoding="utf-8") as f:
                    f.write(html)
                file_count += 1
                new_found += 1

        same_count = same_count + 1 if new_found == 0 else 0
        print(f"Products collected: {len(seen_ids)} | this scroll: {new_found}")


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(viewport={"width": 1400, "height": 1000})
        try:
            scrape_flipkart(page)
            scrape_nykaa(page)
            scrape_puma(page)
        finally:
            browser.close()


if __name__ == "__main__":
    main()
