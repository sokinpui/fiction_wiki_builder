import argparse  # Import argparse
import logging
import os
import re
import zipfile

from elasticsearch import Elasticsearch, helpers

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)

# --- Configuration ---
# BOOKS_DIR will now come from CLI args
ES_HOST = "http://localhost:9200"
# If you enabled security and have a password:
# ES_HOST = 'http://elastic:P@ssw0rd@localhost:9200' # Or your actual credentials


# --- Main Script ---
def get_book_id_from_filename(filename):
    """
    Extracts book ID if filename strictly matches 'book_<digits>.zip'.
    Returns the ID (string) or None if it doesn't match or has extra names.
    """
    match = re.fullmatch(r"book_(\d+)\.zip", filename)
    if match:
        return match.group(1)
    return None


def create_index_if_not_exists(es_client, index_name):
    """Creates an ES index with a basic mapping if it doesn't exist."""
    if not es_client.indices.exists(index=index_name):
        mapping = {
            "mappings": {
                "properties": {
                    "chapter_number": {"type": "integer"},
                    "chapter_name": {"type": "keyword"},
                    "chapter_content": {"type": "text", "analyzer": "standard"},
                }
            }
        }
        try:
            es_client.indices.create(index=index_name, body=mapping)
            logging.info(f"Created index: {index_name}")
        except Exception as e:
            logging.error(f"Failed to create index {index_name}: {e}")
            return False
    return True


def process_book(es_client, zip_filepath, book_id):
    """Processes a single book zip file and ingests its chapters into Elasticsearch."""
    index_name = f"book_{book_id}"

    if not create_index_if_not_exists(es_client, index_name):
        return 0

    actions = []
    chapters_processed = 0

    try:
        with zipfile.ZipFile(zip_filepath, "r") as zf:
            logging.info(f"Processing book: {zip_filepath} for index {index_name}")
            for member_info in zf.infolist():
                if (
                    not member_info.is_dir()
                    and member_info.filename.endswith(".txt")
                    and "/" in member_info.filename
                ):
                    try:
                        chapter_filename = os.path.basename(member_info.filename)
                        chapter_num_str = os.path.splitext(chapter_filename)[0]
                        chapter_number = int(chapter_num_str)

                        with zf.open(member_info.filename) as chapter_file:
                            content = chapter_file.read().decode(
                                "utf-8", errors="ignore"
                            )

                        doc = {
                            "chapter_number": chapter_number,
                            "chapter_name": chapter_filename,
                            "chapter_content": content.strip(),
                        }
                        actions.append({"_index": index_name, "_source": doc})
                        chapters_processed += 1

                    except ValueError:
                        logging.warning(
                            f"Could not parse chapter number from '{member_info.filename}' in {zip_filepath}. Skipping."
                        )
                    except Exception as e:
                        logging.error(
                            f"Error processing chapter '{member_info.filename}' in {zip_filepath}: {e}"
                        )

            if actions:
                helpers.bulk(es_client, actions)
                logging.info(
                    f"Successfully bulk indexed {len(actions)} chapters for {index_name}"
                )

    except zipfile.BadZipFile:
        logging.error(f"Bad zip file: {zip_filepath}. Skipping.")
    except Exception as e:
        logging.error(
            f"An unexpected error occurred while processing {zip_filepath}: {e}"
        )
    return chapters_processed


def main():
    # --- Argument Parsing ---
    parser = argparse.ArgumentParser(
        description="Ingest book chapters from ZIP files into Elasticsearch."
    )
    parser.add_argument(
        "books_directory",
        nargs="?",  # Makes the argument optional
        default=".",  # Default to current directory if not provided
        help="Directory containing the book_*.zip files. Defaults to the current directory.",
    )
    parser.add_argument(
        "--es-host",
        default=ES_HOST,
        help=f"Elasticsearch host URL. Defaults to {ES_HOST}",
    )
    args = parser.parse_args()

    books_dir = args.books_directory
    es_host_url = args.es_host

    if not os.path.isdir(books_dir):
        logging.error(
            f"Error: The specified directory '{books_dir}' does not exist or is not a directory."
        )
        return
    logging.info(f"Using books directory: {os.path.abspath(books_dir)}")
    logging.info(f"Connecting to Elasticsearch at: {es_host_url}")

    try:
        es = Elasticsearch(es_host_url, request_timeout=30)
        if not es.ping():
            logging.error(f"Failed to connect to Elasticsearch at {es_host_url}")
            return
        logging.info(f"Successfully connected to Elasticsearch at {es_host_url}")
    except Exception as e:
        logging.error(f"Elasticsearch connection error: {e}")
        return

    total_books_processed = 0
    total_chapters_ingested = 0

    for filename in os.listdir(books_dir):  # Use the parsed books_dir
        book_id = get_book_id_from_filename(filename)
        if book_id:
            zip_filepath = os.path.join(books_dir, filename)  # Use the parsed books_dir
            if os.path.isfile(zip_filepath):
                logging.info(f"Found valid book file: {filename}, Book ID: {book_id}")
                chapters_count = process_book(es, zip_filepath, book_id)
                if chapters_count > 0:
                    total_books_processed += 1
                    total_chapters_ingested += chapters_count
            else:
                logging.warning(
                    f"Matched pattern but {zip_filepath} is not a file. Skipping."
                )
        elif filename.endswith(".zip"):
            logging.info(
                f"Skipping named or improperly formatted book file: {filename}"
            )

    logging.info(f"\n--- Summary ---")
    logging.info(f"Total books processed: {total_books_processed}")
    logging.info(f"Total chapters ingested: {total_chapters_ingested}")
    logging.info("Script finished.")


if __name__ == "__main__":
    main()
