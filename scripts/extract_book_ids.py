import argparse
import logging
import re
import time

import requests  # Keep for direct fetch if Selenium fails or for other uses
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium.webdriver.chrome.service import (
    Service as ChromeService,
)  # For modern Selenium
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import (
    ChromeDriverManager,
)  # Auto-installs/manages ChromeDriver

# --- Logging Setup ---
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuration (fetch_page_content can be removed if only using Selenium for main page) ---
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
# REQUEST_TIMEOUT etc. might still be used if you fetch other pages directly


def extract_ids_from_html(html_content):  # Same as your original script
    if not html_content:
        return set()
    soup = BeautifulSoup(html_content, "html.parser")
    book_ids = set()
    # Using a more general selector that seemed to work for your example HTML
    # <div class="item"> ... <a href="/read/BOOK_ID/"> ... </a> ... </div>
    item_links = soup.select(
        "div.item a[href]"
    )  # Select all 'a' tags with href inside 'div.item'
    for link_tag in item_links:
        href = link_tag.get("href")
        if href:
            match = re.search(r"/read/(\d+)/?", href)
            if match:
                book_ids.add(match.group(1))
    return book_ids


def get_page_source_with_selenium(url, scrolls=5, scroll_pause_time=3):
    """
    Fetches page source after scrolling using Selenium.
    """
    driver = None
    try:
        logging.info("Initializing Selenium WebDriver...")
        # Automatically download and manage ChromeDriver
        service = ChromeService(ChromeDriverManager().install())
        options = webdriver.ChromeOptions()
        options.add_argument("--headless")  # Run in headless mode (no browser UI)
        options.add_argument("--disable-gpu")  # Recommended for headless
        options.add_argument(
            "--no-sandbox"
        )  # Bypass OS security model, REQUIRED for Docker/Linux CI
        options.add_argument(
            "--disable-dev-shm-usage"
        )  # Overcome limited resource problems
        options.add_argument(f'user-agent={HEADERS["User-Agent"]}')  # Set user agent

        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(30)  # Timeout for page load

        logging.info(f"WebDriver initialized. Fetching URL: {url}")
        driver.get(url)
        time.sleep(scroll_pause_time)  # Allow initial page load and JS to settle

        last_height = driver.execute_script("return document.body.scrollHeight")

        for i in range(scrolls):
            logging.info(f"Scrolling down (Attempt {i + 1}/{scrolls})...")
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(scroll_pause_time)  # Wait for new content to load

            new_height = driver.execute_script("return document.body.scrollHeight")
            if new_height == last_height:
                logging.info(
                    "Reached end of scrollable content or no new content loaded."
                )
                break
            last_height = new_height

        logging.info("Finished scrolling. Getting page source.")
        page_source = driver.page_source
        return page_source
    except TimeoutException:
        logging.error(f"Timeout loading page: {url}")
        return None
    except WebDriverException as e:
        logging.error(f"WebDriverException occurred: {e}")
        return None
    except Exception as e:
        logging.error(f"An unexpected error occurred with Selenium: {e}")
        return None
    finally:
        if driver:
            logging.info("Quitting Selenium WebDriver.")
            driver.quit()


def main():
    parser = argparse.ArgumentParser(
        description="Extract book IDs from a webpage (handles infinite scroll using Selenium) and save them to a file."
    )
    parser.add_argument("url", help="The URL of the webpage containing links to books.")
    parser.add_argument(
        "--output_file",
        default="book_ids.txt",
        help="The file to save the extracted book IDs to (default: book_ids.txt).",
    )
    parser.add_argument(
        "--scrolls",
        type=int,
        default=10,
        help="Number of times to scroll down the page (default: 10).",
    )
    parser.add_argument(
        "--scroll_pause",
        type=float,
        default=3.0,
        help="Seconds to wait between scrolls for content to load (default: 3.0).",
    )

    args = parser.parse_args()

    logging.info(f"Fetching page with Selenium: {args.url}")
    html_content = get_page_source_with_selenium(
        args.url, scrolls=args.scrolls, scroll_pause_time=args.scroll_pause
    )

    if not html_content:
        logging.error("Failed to fetch page content using Selenium. Exiting.")
        return

    logging.info("Extracting book IDs from Selenium-retrieved HTML content...")
    extracted_ids = extract_ids_from_html(html_content)

    if not extracted_ids:
        logging.warning("No book IDs found on the page after scrolling.")
        return

    logging.info(f"Found {len(extracted_ids)} unique book IDs.")

    try:
        with open(args.output_file, "w", encoding="utf-8") as f:
            for book_id in sorted(list(extracted_ids), key=int):  # Sort numerically
                f.write(f"{book_id}\n")
        logging.info(
            f"Successfully saved {len(extracted_ids)} book IDs to {args.output_file}"
        )
    except IOError as e:
        logging.error(f"Failed to write book IDs to {args.output_file}: {e}")


if __name__ == "__main__":
    main()
