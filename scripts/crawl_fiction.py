import argparse
import logging
import os
import re
import threading
import time
from urllib.parse import urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

# --- Global Constants (will be updated by CLI args) ---
# These will be set in main() based on args
BASE_URL_TEMPLATE = ""
BOOK_ID = ""
OUTPUT_DIR_BASE = "downloaded_books"  # Default, can be changed by CLI
BOOK_OUTPUT_DIR = ""  # Will be OUTPUT_DIR_BASE + book_BOOK_ID

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
}
REQUEST_TIMEOUT = 20
RETRY_ATTEMPTS = 3
RETRY_DELAY = 5
POLITENESS_DELAY_PER_THREAD = 1.0  # Delay after a thread saves a chapter
SUB_PAGE_DELAY = 0.2

MAX_CONSECUTIVE_CHAPTER_FAILURES_PER_THREAD = 2

# --- Logging Setup ---
# Configure logging before any threads might use it.
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(threadName)s - %(levelname)s - %(message)s",
)

# --- Promo Text for Removal ---
# Regexes to catch variations, case-insensitive, and DOTALL for multiline matches if needed
PROMO_TEXTS_TO_REMOVE_PATTERNS = [
    re.compile(r"ahref=cmfu起点中文网.*?尽在起点原创！", re.IGNORECASE | re.DOTALL),
    re.compile(r"f=cmfu起点中文网.*?尽在起点原创！", re.IGNORECASE | re.DOTALL),
    re.compile(r"起点中文网.*?欢迎广大书友光临阅读", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"最新、最快、最火的连载作品尽在(?:起点原创)?(?:！)?", re.IGNORECASE | re.DOTALL
    ),
    re.compile(r"欢迎广大书友光临阅读", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"请收藏：\s*https?://[a-zA-Z0-9.-/]+", re.IGNORECASE | re.DOTALL
    ),  # Existing收藏 line
    re.compile(r"手机用户请到m\.起点中文网阅读", re.IGNORECASE | re.DOTALL),
    re.compile(
        r"target=_blank>起点中文网</a>", re.IGNORECASE | re.DOTALL
    ),  # HTML entity version
]


def parse_url_and_book_id(sample_url):
    """
    Parses a sample chapter URL to extract the base URL template and book ID.
    Example: https://domain.com/index/12345/1.html
    Returns (base_template, book_id) or (None, None) on failure.
    """
    try:
        parsed_url = urlparse(sample_url)
        path_segments = [
            seg for seg in parsed_url.path.split("/") if seg
        ]  # Get non-empty path segments

        # Expect structure like: ..., 'index', BOOK_ID, CHAPTER_INFO.html
        # Find 'index', then BOOK_ID is the next segment
        if "index" in path_segments:
            index_pos = path_segments.index("index")
            if index_pos + 1 < len(path_segments):
                book_id_str = path_segments[index_pos + 1]
                if book_id_str.isdigit():
                    book_id = book_id_str

                    # Reconstruct base path up to 'index'
                    # Example: if path_segments = ['path1', 'index', '123', 'chap.html']
                    # base_path_prefix_segments = ['path1']
                    base_path_prefix_segments = path_segments[:index_pos]
                    base_path_prefix = (
                        "/" + "/".join(base_path_prefix_segments)
                        if base_path_prefix_segments
                        else ""
                    )

                    template_path = (
                        f"{base_path_prefix}/index/{{book_id}}/{{chapter_page_id}}.html"
                    )

                    template = urlunparse(
                        (
                            parsed_url.scheme,
                            parsed_url.netloc,
                            template_path,
                            "",
                            "",
                            "",
                        )
                    )
                    return template, book_id

        logging.error(
            f"Could not parse BOOK_ID and template from URL: {sample_url}. Path segments: {path_segments}"
        )
        return None, None
    except Exception as e:
        logging.error(f"Error parsing URL {sample_url}: {e}")
        return None, None


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
            # General cleaning for title from <title> tag
            page_title_text = re.sub(
                r" - .*$|\|.*$|_凡人修仙传.*$|在线阅读.*$|_小说.*$|_笔趣阁.*$",
                "",
                page_title_text,
                flags=re.I,
            ).strip()
            if page_title_text and len(page_title_text) < 150:
                extracted_chapter_title = page_title_text

    content_div = soup.find("div", id="chaptercontent", class_="Readarea")
    if not content_div:
        # Try another common pattern if the primary one fails
        content_div = soup.find("div", id="content")
        if not content_div:
            content_div = soup.find("div", class_="content")
            if not content_div:
                logging.warning(
                    f"Could not find main content div for title: '{extracted_chapter_title}'."
                )
                return None, extracted_chapter_title

    # Remove known non-content elements
    for unwanted_selector in [
        "p.noshow",
        "div.chapter_note",
        "div.bottom_related",
        "div.footer_link",
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

    # Get text from remaining elements
    text_parts = []
    for element in content_div.contents:
        if element.name == "br":
            text_parts.append("\n")
        elif isinstance(element, str):  # NavigableString
            text_parts.append(str(element))
        elif element.name == "p":  # Handle paragraphs explicitly to ensure newlines
            text_parts.append(
                element.get_text(strip=False) + "\n\n"
            )  # Add double newline after P
        elif hasattr(element, "get_text"):  # Other tags
            text_parts.append(element.get_text(strip=False))

    full_text = "".join(text_parts)

    # Remove specific promo texts using compiled regex patterns
    for pattern in PROMO_TEXTS_TO_REMOVE_PATTERNS:
        full_text = pattern.sub("", full_text)

    # Normalize whitespace and paragraph breaks
    full_text = re.sub(r"\n\s*\n+", "\n\n", full_text)  # Consolidate multiple newlines
    full_text = (
        full_text.strip()
    )  # Remove leading/trailing whitespace from the whole block

    return full_text if full_text else None, extracted_chapter_title


def save_chapter(chapter_num_str, title, content, current_book_output_dir):
    if not os.path.exists(current_book_output_dir):
        try:
            os.makedirs(current_book_output_dir, exist_ok=True)
        except OSError as e:
            logging.error(
                f"Could not create book output directory {current_book_output_dir}: {e}"
            )
            return

    safe_title = re.sub(r"[^\w\s.-]", "", title).strip()
    safe_title = re.sub(r"[-\s]+", "_", safe_title)
    if not safe_title:
        safe_title = "chapter"  # Fallback if title becomes empty after sanitizing

    filename = f"{chapter_num_str}_{safe_title}.txt"

    # Truncate filename if too long (considering OS limits and UTF-8 encoding)
    max_filename_bytes = 250  # OS limit often 255 bytes, leave a margin
    if len(filename.encode("utf-8")) > max_filename_bytes:
        name_part, ext_part = os.path.splitext(filename)
        # Iteratively shorten name_part until its byte length is acceptable
        while (
            len(name_part.encode("utf-8"))
            > max_filename_bytes - len(ext_part.encode("utf-8")) - 1
        ):  # -1 for the dot
            if not name_part:
                break  # Safety break if name_part becomes empty
            name_part = name_part[:-1]
        filename = name_part + ext_part
        logging.warning(f"Filename was too long, truncated to: {filename}")

    filepath = os.path.join(current_book_output_dir, filename)

    try:
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# {title}\n\n")
            f.write(content)
        logging.info(f"Successfully saved: {filepath}")
    except IOError as e:
        logging.error(f"Failed to save chapter {chapter_num_str} to {filepath}: {e}")


def download_chapter_range(
    range_start_chapter,
    range_end_chapter,
    current_book_id,
    current_base_url_template,
    current_book_output_dir,
):
    """Worker function for threads to download a specific range of chapters."""
    logging.info(
        f"Thread started for chapter range: {range_start_chapter}-{range_end_chapter}"
    )
    consecutive_failures_in_thread = 0

    for chapter_num_to_try in range(range_start_chapter, range_end_chapter + 1):
        if (
            consecutive_failures_in_thread
            >= MAX_CONSECUTIVE_CHAPTER_FAILURES_PER_THREAD
        ):
            logging.warning(
                f"Thread stopping for range {range_start_chapter}-{range_end_chapter}: Exceeded {MAX_CONSECUTIVE_CHAPTER_FAILURES_PER_THREAD} consecutive failures."
            )
            break

        collected_content_for_this_chapter = []
        title_for_this_chapter = f"Chapter {chapter_num_to_try}"  # Default
        first_page_of_this_chapter_processed_ok = False

        current_sub_page_num = 1
        while True:  # Loop for sub-pages (N, N_2, N_3...)
            if current_sub_page_num == 1:
                chapter_page_id_segment = str(chapter_num_to_try)
            else:
                chapter_page_id_segment = f"{chapter_num_to_try}_{current_sub_page_num}"

            url = current_base_url_template.format(
                book_id=current_book_id, chapter_page_id=chapter_page_id_segment
            )

            html_content = fetch_url(url)

            if html_content is None:  # Page not found or fetch error
                if current_sub_page_num == 1:
                    consecutive_failures_in_thread += 1
                    logging.debug(
                        f"Failed primary page for chapter {chapter_num_to_try}. Consecutive failures in thread: {consecutive_failures_in_thread}"
                    )
                else:
                    logging.debug(
                        f"No more sub-pages for chapter {chapter_num_to_try} after '_{current_sub_page_num - 1}'."
                    )
                break  # Exit sub-page loop

            if current_sub_page_num == 1:  # Successfully fetched a chapter's first page
                consecutive_failures_in_thread = 0
                first_page_of_this_chapter_processed_ok = True

            extracted_text, extracted_title = extract_chapter_content(html_content)

            if not extracted_text:
                logging.warning(
                    f"No content extracted from {url}, though page fetched."
                )
                if current_sub_page_num == 1:
                    consecutive_failures_in_thread += 1
                    first_page_of_this_chapter_processed_ok = False
                    logging.debug(
                        f"Primary page for chapter {chapter_num_to_try} yielded no content. Consecutive failures in thread: {consecutive_failures_in_thread}"
                    )
                else:
                    logging.debug(
                        f"Sub-page {url} yielded no content. Assuming end of pages for chapter {chapter_num_to_try}."
                    )
                break

            collected_content_for_this_chapter.append(extracted_text)
            if (
                current_sub_page_num == 1
                and extracted_title
                and extracted_title.lower() != "untitled chapter"
            ):
                title_for_this_chapter = extracted_title

            logging.debug(
                f"Processed page: {chapter_page_id_segment} for chapter {chapter_num_to_try}. Content len: {len(extracted_text)}"
            )
            current_sub_page_num += 1
            if current_sub_page_num > 1:  # Small delay only for sub-pages
                time.sleep(SUB_PAGE_DELAY)

        if collected_content_for_this_chapter:
            full_chapter_text = "\n\n".join(collected_content_for_this_chapter)
            filename_chapter_prefix = f"{chapter_num_to_try:04d}"  # Padded for sorting
            save_chapter(
                filename_chapter_prefix,
                title_for_this_chapter,
                full_chapter_text,
                current_book_output_dir,
            )
            time.sleep(POLITENESS_DELAY_PER_THREAD)
        elif not first_page_of_this_chapter_processed_ok and current_sub_page_num == 1:
            logging.debug(
                f"Chapter {chapter_num_to_try} skipped by thread as its first page was not successfully processed."
            )

    logging.info(
        f"Thread finished for chapter range: {range_start_chapter}-{range_end_chapter}"
    )


def main():
    parser = argparse.ArgumentParser(
        description="Crawl a fiction book from a given URL structure using multiple threads."
    )
    parser.add_argument(
        "url",
        help="A sample chapter URL (e.g., https://domain.com/index/BOOK_ID/CHAPTER_ID.html) from which the Book ID and base URL structure will be derived.",
    )
    parser.add_argument(
        "--start_chapter",
        type=int,
        default=1,
        help="Chapter number to start downloading from (default: 1).",
    )
    parser.add_argument(
        "--end_chapter",
        type=int,
        default=2000,
        help="Chapter number to download up to (inclusive, default: 2000).",
    )
    parser.add_argument(
        "--threads",
        type=int,
        default=4,
        choices=range(1, 33),
        metavar="[1-32]",
        help="Number of concurrent download threads (default: 4, max: 32).",
    )
    parser.add_argument(
        "--output",
        default="downloaded_books",
        help="Base directory to save downloaded books (default: downloaded_books).",
    )

    args = parser.parse_args()

    if args.threads <= 0:
        parser.error("Number of threads must be positive.")

    # Use global variables for these, as they are set once and read by threads
    global BASE_URL_TEMPLATE, BOOK_ID, OUTPUT_DIR_BASE, BOOK_OUTPUT_DIR

    OUTPUT_DIR_BASE = args.output
    parsed_template, parsed_book_id = parse_url_and_book_id(args.url)

    if not parsed_template or not parsed_book_id:
        logging.error(
            "Could not derive necessary URL template or Book ID from the provided URL. Please check the URL format. Exiting."
        )
        return

    BASE_URL_TEMPLATE = parsed_template
    BOOK_ID = parsed_book_id
    BOOK_OUTPUT_DIR = os.path.join(
        OUTPUT_DIR_BASE, f"book_{BOOK_ID}"
    )  # Specific path for this book

    logging.info(f"Target Book ID: {BOOK_ID}")
    logging.info(f"Base URL Template: {BASE_URL_TEMPLATE}")
    logging.info(f"Output Directory for this book: {BOOK_OUTPUT_DIR}")
    logging.info(
        f"Downloading chapters from {args.start_chapter} to {args.end_chapter} using {args.threads} threads."
    )

    # Create output directories if they don't exist
    try:
        os.makedirs(
            BOOK_OUTPUT_DIR, exist_ok=True
        )  # exist_ok=True handles concurrent creation well
    except OSError as e:
        logging.error(
            f"Could not create output directory {BOOK_OUTPUT_DIR}: {e}. Exiting."
        )
        return

    threads_list = []
    total_chapters_to_process = args.end_chapter - args.start_chapter + 1
    if total_chapters_to_process <= 0:
        logging.info(
            "Start chapter is greater than end chapter. No chapters to download."
        )
        return

    # Calculate chapters per thread, ensuring all chapters are covered
    chapters_per_thread_base = total_chapters_to_process // args.threads
    remainder_chapters = total_chapters_to_process % args.threads

    current_chapter_assignment_start = args.start_chapter

    for i in range(args.threads):
        num_chapters_for_this_thread = chapters_per_thread_base + (
            1 if i < remainder_chapters else 0
        )

        if num_chapters_for_this_thread == 0:  # No chapters left for this thread
            continue

        range_s = current_chapter_assignment_start
        range_e = current_chapter_assignment_start + num_chapters_for_this_thread - 1

        # Ensure range_e does not exceed the overall end_chapter
        range_e = min(range_e, args.end_chapter)

        if range_s > range_e:  # Should not happen with correct logic but as a safeguard
            continue

        # Pass BOOK_ID, BASE_URL_TEMPLATE, and BOOK_OUTPUT_DIR to each thread's worker function
        thread = threading.Thread(
            target=download_chapter_range,
            args=(range_s, range_e, BOOK_ID, BASE_URL_TEMPLATE, BOOK_OUTPUT_DIR),
            name=f"Downloader-{i+1}",
        )
        threads_list.append(thread)
        thread.start()

        current_chapter_assignment_start = (
            range_e + 1
        )  # Next thread starts after this one ends

    for thread in threads_list:
        thread.join()

    logging.info("All download threads have completed.")


if __name__ == "__main__":
    main()
