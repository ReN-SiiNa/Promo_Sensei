from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os

# Initialize Chrome WebDriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# Correct way: wrap driver path in a Service object
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# --- Flipkart scraping ---
query_flipkart = "sale"
file_flipkart = 0
os.makedirs("data/flipkart", exist_ok=True)

for i in range(1, 20):
    url = f"https://www.flipkart.com/search?q={query_flipkart}&sort=relevance&page={i}"
    print(f"Loading Flipkart page {i}...")
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.XPATH, '//div[@data-id]'))
        )
    except Exception as e:
        print(f"Timeout or error on Flipkart page {i}: {e}")
        continue

    elems = driver.find_elements(By.XPATH, '//div[@data-id]')
    print(f"{len(elems)} Flipkart items found on page {i}")

    for elem in elems:
        html = elem.get_attribute("outerHTML")
        with open(f"data/flipkart/{query_flipkart}_{file_flipkart}.html", "w", encoding="utf-8") as f:
            f.write(html)
        file_flipkart += 1

# --- Nykaa scraping ---
query_nykaa = "bestsellers"
base_url_nykaa = "https://www.nykaa.com/bestsellers/c/15752"
file_nykaa = 0
os.makedirs("data/nykaa", exist_ok=True)

for page in range(1, 20):
    url = f"{base_url_nykaa}?page_no={page}&sort=discount"
    print(f"Loading Nykaa page {page}...")
    driver.get(url)

    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div#product-list-wrap > div.productWrapper"))
        )
    except Exception as e:
        print(f"Timeout or error on Nykaa page {page}: {e}")
        continue

    elems = driver.find_elements(By.CSS_SELECTOR, "div#product-list-wrap > div.productWrapper")
    print(f"{len(elems)} Nykaa products found on page {page}")

    for elem in elems:
        html = elem.get_attribute("outerHTML")
        with open(f"data/nykaa/{query_nykaa}_{file_nykaa}.html", "w", encoding="utf-8") as f:
            f.write(html)
        file_nykaa += 1

# --- Puma scraping ---
driver.get("https://in.puma.com/in/en/puma-sale-collection?sort=Discount-high-to-low")
os.makedirs("data/puma", exist_ok=True)

# Scroll & load settings
scroll_pause_time = 2
seen_ids = set()
file_count = 0
same_count = 0
max_same_scrolls = 5  # stop if no new products after 5 scrolls

def scroll_down():
    driver.execute_script("window.scrollBy(0, 1000);")

print("Starting scroll and scrape...")

while same_count < max_same_scrolls:
    scroll_down()
    time.sleep(scroll_pause_time)

    products = driver.find_elements(By.CSS_SELECTOR, "ul#product-list-items > li[data-test-id='product-list-item']")
    new_found = 0

    for p in products:
        pid = p.get_attribute("data-product-id")
        if pid and pid not in seen_ids:
            seen_ids.add(pid)
            html = p.get_attribute("outerHTML")
            with open(f"data/puma/product_{file_count}.html", "w", encoding="utf-8") as f:
                f.write(html)
            file_count += 1
            new_found += 1

    if new_found == 0:
        same_count += 1
    else:
        same_count = 0  # reset if new items found

    print(f"Products collected: {len(seen_ids)} | This scroll: {new_found}")

driver.quit()