# File: scripts/extract_knowledge.py

import argparse
import logging
import os

from src.fwb.generative.gemini.gemini_model import GeminiLLMHandler
from src.fwb.knowledge_extraction.data_store import KnowledgeDataStore
from src.fwb.knowledge_extraction.extractor import KnowledgeExtractor

# Setup basic logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.StreamHandler()
        # You can add logging.FileHandler("extraction.log") here if needed
    ],
)
# Set higher level for verbose libraries if needed
logging.getLogger("elasticsearch").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


logger = logging.getLogger(__name__)


def main():
    parser = argparse.ArgumentParser(
        description="Extract knowledge from a book using AI and store in Elasticsearch."
    )
    parser.add_argument(
        "book_id",
        type=str,
        help="The ID of the book to process (e.g., '123' for index 'book_123').",
    )
    parser.add_argument(
        "--es-host",
        default=os.environ.get("ES_HOST", "http://localhost:9200"),
        help="Elasticsearch host URL. Defaults to ES_HOST env var or http://localhost:9200.",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("GENAI_API_KEY"),
        help="Gemini API Key. Defaults to GENAI_API_KEY env var.",
    )

    args = parser.parse_args()

    if not args.api_key:
        logger.error(
            "GENAI_API_KEY is required. Set it as an environment variable or pass --api-key."
        )
        return

    logger.info(f"Starting knowledge extraction for Book ID: {args.book_id}")
    logger.info(f"Elasticsearch Host: {args.es_host}")

    try:
        # 1. Initialize Gemini LLM Handler
        # The GeminiLLMHandler already reads GENAI_API_KEY from env or constructor
        llm_handler = GeminiLLMHandler(api_key=args.api_key)

        # 2. Initialize Knowledge Data Store
        data_store = KnowledgeDataStore(es_host=args.es_host)

        # 3. Initialize Knowledge Extractor
        extractor = KnowledgeExtractor(llm_handler=llm_handler, data_store=data_store)

        # 4. Process the book
        extractor.process_book(args.book_id)

        logger.info(
            f"Knowledge extraction process completed for Book ID: {args.book_id}"
        )

    except ConnectionError as ce:
        logger.error(f"Connection error: {ce}")
    except ValueError as ve:
        logger.error(f"Configuration error: {ve}")
    except Exception as e:
        logger.error(f"An unexpected error occurred: {e}", exc_info=True)


if __name__ == "__main__":
    # Make sure the src directory is in PYTHONPATH or run as a module
    # For simple execution from project root:
    # export PYTHONPATH=$PYTHONPATH:./
    # python scripts/extract_knowledge.py <book_id>
    main()
