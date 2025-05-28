import argparse
import logging
import os
import re
import time
import zipfile

import requests
from bs4 import BeautifulSoup

# import threading # If you want to re-introduce multithreading later

# --- Global Configuration (can be adjusted) ---
CHAPTER_URL_TEMPLATE = (
    "https://8520b295ef767.ae2e.cc/kan/{book_id}/{chapter_page_id}.html"
)
DEFAULT_OUTPUT_BASE_DIR = "downloaded_fiction"  # Define a constant for the default

# These will be set in main based on args or default
OUTPUT_BASE_DIR = DEFAULT_OUTPUT_BASE_DIR  # Initialize with default

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
REQUEST_TIMEOUT = 20
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
POLITENESS_DELAY_CHAPTER = 1.0
SUB_PAGE_DELAY = 0.25
MAX_CONSECUTIVE_CHAPTER_FAILURES_PER_BOOK = 5
MAX_SUB_PAGES_TO_TRY = 20

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

PROMO_TEXTS_TO_REMOVE_PATTERNS = [
    re.compile(r"ahref=cmfu起点中文网.*?尽在起点原创！", re.IGNORECASE | re.DOTALL),
    re.compile(r"f=cmfu起点中文网.*?尽在起点原创！", re.IGNORECASE | re.DOTALL),
    re.compile(r"起点中文网.*?欢迎广大书友光临阅读", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"最新、最快、最火的连载作品尽在(?:起点原创)?(?:！)?", re.IGNORECASE | re.DOTALL
    ),
    re.compile(r"欢迎广大书友光临阅读", re.IGNORECASE | re.DOTALL),
    re.compile(r"请收藏：\s*https?://[a-zA-Z0-9.-/]+", re.IGNORECASE | re.DOTALL),
    re.compile(r"手机用户请到m\.起点中文网阅读", re.IGNORECASE | re.DOTALL),
    re.compile(r"target=_blank>起点中文网</a>", re.IGNORECASE | re.DOTALL),
]


def fetch_url(url):
    for attempt in range(RETRY_ATTEMPTS):
        try:
            response = requests.get(url, headers=HEADERS, timeout=REQUEST_TIMEOUT)
            response.raise_for_status()
            try:
                content = response.content.decode("utf-8")
            except UnicodeDecodeError:
                try:
                    content = response.content.decode("gbk")
                except UnicodeDecodeError:
                    content = response.content.decode("latin-1", errors="ignore")
            return content
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logging.debug(f"Page not found (404): {url}")
                return None
            logging.warning(
                f"HTTP error {e.response.status_code} for {url} (Attempt {attempt + 1}/{RETRY_ATTEMPTS})"
            )
        except requests.exceptions.RequestException as e:
            logging.warning(
                f"Request failed for {url}: {e} (Attempt {attempt + 1}/{RETRY_ATTEMPTS})"
            )
        if attempt < RETRY_ATTEMPTS - 1:
            logging.info(f"Retrying in {RETRY_DELAY} seconds for {url}...")
            time.sleep(RETRY_DELAY)
    return None


def extract_chapter_content(html_content):
    if not html_content:
        return None, None
    soup = BeautifulSoup(html_content, "html.parser")
    extracted_chapter_title = "Untitled Chapter"

    header_div = soup.find("div", class_="header")
    if header_div:
        title_span = header_div.find("span", class_="title")
        if title_span:
            raw_title_text = title_span.get_text(strip=True)
            parts = raw_title_text.split("_", 1)
            extracted_chapter_title = parts[0].strip() if parts else raw_title_text
    else:
        page_html_title_tag = soup.find("title")
        if page_html_title_tag:
            page_title_text = page_html_title_tag.get_text(strip=True)
            page_title_text = re.sub(
                r" - .*$|\|.*$|_凡人修仙传.*$|在线阅读.*$|_小说.*$|_笔趣阁.*$",
                "",
                page_title_text,
                flags=re.I,
            ).strip()
            if page_title_text and len(page_title_text) < 150:
                extracted_chapter_title = page_title_text
        elif soup.find("h1"):
            extracted_chapter_title = soup.find("h1").get_text(strip=True)

    content_div = soup.find("div", id="chaptercontent")
    if not content_div:
        content_div = soup.find("div", id="content")
        if not content_div:
            content_div = soup.find("div", class_="content")
            if not content_div:
                logging.warning(
                    f"Could not find main content div for title: '{extracted_chapter_title}'."
                )
                return None, extracted_chapter_title

    for unwanted_selector in [
        "p.noshow",
        "div.chapter_note",
        "div.bottom_related",
        "div.footer_link",
        "div.page_nav",
    ]:
        for tag in content_div.select(unwanted_selector):
            tag.decompose()
    for unwanted_tag_name in [
        "script",
        "style",
        "iframe",
        "ins",
        "form",
        "button",
        "object",
        "embed",
        "noscript",
    ]:
        for tag in content_div.find_all(unwanted_tag_name):
            tag.decompose()
    for ad_pattern_text in [
        r"ads",
        r"recommend",
        r"social",
        r"share",
        r"comment",
        r"nav",
        r"banner",
        r"promo",
        r"bottom-bar",
        r"notice",
        r"tip",
    ]:
        ad_regex = re.compile(ad_pattern_text, re.I)
        for ad_element in content_div.find_all(class_=ad_regex):
            ad_element.decompose()
        for ad_element_id in content_div.find_all(id=ad_regex):
            ad_element_id.decompose()

    text_parts = []
    for element in content_div.children:
        if element.name == "br":
            text_parts.append("\n")
        elif element.name == "p":
            text_parts.append(element.get_text(strip=False).strip() + "\n\n")
        elif isinstance(element, str):
            text_parts.append(str(element))
        elif hasattr(element, "get_text"):
            text_parts.append(element.get_text(strip=False))

    full_text = "".join(text_parts)
    for pattern in PROMO_TEXTS_TO_REMOVE_PATTERNS:
        full_text = pattern.sub("", full_text)
    full_text = re.sub(r"\n\s*\n+", "\n\n", full_text)
    full_text = full_text.strip()
    return full_text if full_text else None, extracted_chapter_title


def save_chapter_to_file(chapter_num_for_filename, title, content, book_specific_dir):
    if not os.path.exists(book_specific_dir):
        os.makedirs(book_specific_dir, exist_ok=True)

    safe_title = re.sub(r"[^\w\s.-]", "", title).strip()
    safe_title = re.sub(r"[-\s]+", "_", safe_title)
    if not safe_title:
        safe_title = "chapter"
    filename = f"{chapter_num_for_filename}_{safe_title}.txt"

    max_filename_bytes = 250
    if len(filename.encode("utf-8")) > max_filename_bytes:
        name_part, ext_part = os.path.splitext(filename)
        while (
            len(name_part.encode("utf-8"))
            > max_filename_bytes - len(ext_part.encode("utf-8")) - 1
        ):
            if not name_part:
                break
            name_part = name_part[:-1]
        filename = name_part + ext_part
        logging.warning(
            f"Filename was too long for '{title}', truncated to: {filename}"
        )

    filepath = os.path.join(book_specific_dir, filename)
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(content)
        logging.debug(f"Saved: {filepath}")
    except IOError as e:
        logging.error(
            f"Failed to save chapter {chapter_num_for_filename} to {filepath}: {e}"
        )


def zip_book_directory(book_dir_path, book_id):
    # Use the global OUTPUT_BASE_DIR to determine where the zip file goes
    zip_file_name = f"{book_id}.zip"
    zip_file_path = os.path.join(
        OUTPUT_BASE_DIR, zip_file_name
    )  # Zip in the base output, not inside book_bookid

    logging.info(f"Zipping directory '{book_dir_path}' to '{zip_file_path}'")
    try:
        with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(book_dir_path):
                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, book_dir_path)
                    zf.write(file_path, arcname)
        logging.info(f"Successfully zipped {book_dir_path} to {zip_file_path}")
        # import shutil
        # shutil.rmtree(book_dir_path)
        # logging.info(f"Removed original directory: {book_dir_path}")
    except Exception as e:
        logging.error(f"Failed to zip {book_dir_path}: {e}")


def download_book(book_id, book_output_dir_for_this_book):
    logging.info(f"--- Starting download for Book ID: {book_id} ---")
    current_chapter_num_to_try = 1
    consecutive_main_chapter_failures = 0

    while True:
        if (
            consecutive_main_chapter_failures
            >= MAX_CONSECUTIVE_CHAPTER_FAILURES_PER_BOOK
        ):
            logging.warning(
                f"Book ID {book_id}: Exceeded {MAX_CONSECUTIVE_CHAPTER_FAILURES_PER_BOOK} consecutive main chapter failures. Assuming end of book."
            )
            break

        collected_content_for_this_chapter_num = []
        title_for_this_chapter_num = f"Chapter {current_chapter_num_to_try}"
        first_page_of_this_chapter_num_ok = False
        current_sub_page_index = 1

        while current_sub_page_index <= MAX_SUB_PAGES_TO_TRY:
            if current_sub_page_index == 1:
                chapter_page_id_segment = str(current_chapter_num_to_try)
            else:
                chapter_page_id_segment = (
                    f"{current_chapter_num_to_try}_{current_sub_page_index}"
                )

            url = CHAPTER_URL_TEMPLATE.format(
                book_id=book_id, chapter_page_id=chapter_page_id_segment
            )
            html_content = fetch_url(url)

            if html_content is None:
                if current_sub_page_index == 1:
                    consecutive_main_chapter_failures += 1
                    logging.debug(
                        f"Book {book_id}, Ch {current_chapter_num_to_try}: Failed primary page. Consecutive failures: {consecutive_main_chapter_failures}"
                    )
                else:
                    logging.debug(
                        f"Book {book_id}, Ch {current_chapter_num_to_try}: No more sub-pages after '_{current_sub_page_index - 1}'."
                    )
                break

            if current_sub_page_index == 1:
                consecutive_main_chapter_failures = 0
                first_page_of_this_chapter_num_ok = True

            extracted_text, extracted_title = extract_chapter_content(html_content)

            if not extracted_text:
                logging.warning(
                    f"Book {book_id}, Ch {chapter_page_id_segment}: No content extracted from {url}, though page fetched."
                )
                if current_sub_page_index == 1:
                    consecutive_main_chapter_failures += 1
                    first_page_of_this_chapter_num_ok = False
                break

            collected_content_for_this_chapter_num.append(extracted_text)
            if (
                current_sub_page_index == 1
                and extracted_title
                and extracted_title.lower() != "untitled chapter"
            ):
                title_for_this_chapter_num = extracted_title

            logging.debug(
                f"Book {book_id}, Ch {chapter_page_id_segment}: Processed page. Content len: {len(extracted_text)}"
            )
            current_sub_page_index += 1
            if current_sub_page_index > 1:
                time.sleep(SUB_PAGE_DELAY)

        if collected_content_for_this_chapter_num:
            full_chapter_text = "\n\n".join(collected_content_for_this_chapter_num)
            filename_prefix = f"{current_chapter_num_to_try:04d}"
            save_chapter_to_file(
                filename_prefix,
                title_for_this_chapter_num,
                full_chapter_text,
                book_output_dir_for_this_book,
            )
            time.sleep(POLITENESS_DELAY_CHAPTER)
        elif not first_page_of_this_chapter_num_ok and current_sub_page_index == 1:
            logging.debug(
                f"Book {book_id}, Ch {current_chapter_num_to_try}: Skipped as its first page was not successful."
            )

        if not first_page_of_this_chapter_num_ok and current_sub_page_index == 1:
            pass
        current_chapter_num_to_try += 1

    logging.info(f"--- Finished download attempts for Book ID: {book_id} ---")
    if os.path.exists(book_output_dir_for_this_book) and os.listdir(
        book_output_dir_for_this_book
    ):
        zip_book_directory(book_output_dir_for_this_book, book_id)
    else:
        logging.info(f"No chapters downloaded for Book ID {book_id}, skipping zipping.")


def main():
    parser = argparse.ArgumentParser(
        description="Download books chapter by chapter based on a list of book IDs, then zip each book's directory."
    )
    parser.add_argument(
        "id_file", help="Path to a text file containing book IDs, one ID per line."
    )
    # Use the constant for the default help string
    parser.add_argument(
        "--output_dir",
        default=DEFAULT_OUTPUT_BASE_DIR,
        help=f"Base directory to save downloaded book folders and zips (default: {DEFAULT_OUTPUT_BASE_DIR}).",
    )

    args = parser.parse_args()

    # Declare OUTPUT_BASE_DIR as global here, then assign the value from args
    global OUTPUT_BASE_DIR
    OUTPUT_BASE_DIR = args.output_dir  # This is the correct place to assign from args

    if not os.path.isfile(args.id_file):
        logging.error(f"Book ID file not found: {args.id_file}")
        return

    try:
        with open(args.id_file, "r", encoding="utf-8") as f:
            book_ids_to_process = [line.strip() for line in f if line.strip().isdigit()]
    except IOError as e:
        logging.error(f"Could not read book ID file {args.id_file}: {e}")
        return

    if not book_ids_to_process:
        logging.info("No valid book IDs found in the file.")
        return

    logging.info(f"Found {len(book_ids_to_process)} book IDs to process.")
    logging.info(
        f"Books will be saved under: {OUTPUT_BASE_DIR}"
    )  # Now OUTPUT_BASE_DIR has the correct value

    try:
        os.makedirs(OUTPUT_BASE_DIR, exist_ok=True)
    except OSError as e:
        logging.error(f"Could not create base output directory {OUTPUT_BASE_DIR}: {e}")
        return

    for book_id in book_ids_to_process:
        book_specific_raw_dir = os.path.join(OUTPUT_BASE_DIR, f"book_{book_id}")
        download_book(book_id, book_specific_raw_dir)

    logging.info("All specified books have been processed.")


if __name__ == "__main__":
    main()
