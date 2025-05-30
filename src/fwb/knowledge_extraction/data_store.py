# File: src/fwb/knowledge_extraction/data_store.py

import datetime
import logging
from typing import Any, Dict, Iterator, Optional

from elasticsearch import Elasticsearch, NotFoundError, helpers

logger = logging.getLogger(__name__)


class KnowledgeDataStore:
    def __init__(self, es_host: str, es_client: Optional[Elasticsearch] = None):
        if es_client:
            self.es = es_client
        else:
            self.es = Elasticsearch(es_host, request_timeout=30)

        if not self.es.ping():
            logger.error(f"Failed to connect to Elasticsearch at {es_host}")
            raise ConnectionError(f"Failed to connect to Elasticsearch at {es_host}")
        logger.info(f"Successfully connected to Elasticsearch at {es_host}")

    def get_chapters(self, book_id: str) -> Iterator[Dict[str, Any]]:
        """
        Fetches all chapters for a given book_id, ordered by chapter_number.
        """
        source_index_name = f"book_{book_id}"
        if not self.es.indices.exists(index=source_index_name):
            logger.warning(
                f"Source index {source_index_name} does not exist. No chapters to process."
            )
            return iter([])

        query = {"query": {"match_all": {}}, "sort": [{"chapter_number": "asc"}]}

        try:
            # Using scan helper for large result sets
            for hit in helpers.scan(self.es, query=query, index=source_index_name):
                yield hit["_source"]
        except NotFoundError:
            logger.warning(f"Source index {source_index_name} not found during scan.")
            return iter([])
        except Exception as e:
            logger.error(
                f"Error fetching chapters from {source_index_name}: {e}", exc_info=True
            )
            return iter([])

    def create_knowledge_index_if_not_exists(self, book_id: str) -> bool:
        """
        Creates the knowledge index for a book if it doesn't exist.
        The mapping is dynamic for now, can be refined later.
        """
        index_name = f"knowledge_book_{book_id}"
        if not self.es.indices.exists(index=index_name):
            try:
                # A simple mapping, ES will dynamically map fields within the 'knowledge' object
                mapping = {
                    "mappings": {
                        "properties": {
                            "book_id": {"type": "keyword"},
                            "chapter_number": {"type": "integer"},
                            "extracted_at": {"type": "date"},
                            "knowledge": {
                                "type": "object",
                                "enabled": True,
                            },  # Allows for nested JSON
                        }
                    }
                }
                self.es.indices.create(index=index_name, body=mapping)
                logger.info(f"Created knowledge index: {index_name}")
                return True
            except Exception as e:
                logger.error(
                    f"Failed to create knowledge index {index_name}: {e}", exc_info=True
                )
                return False
        return True

    def store_knowledge(
        self, book_id: str, chapter_number: int, enriched_knowledge_data: Dict[str, Any]
    ) -> bool:
        """
        Stores the enriched knowledge data for a specific chapter.
        Each call creates one document in the knowledge_book_<id> index.
        """
        index_name = f"knowledge_book_{book_id}"
        if not self.create_knowledge_index_if_not_exists(
            book_id
        ):  # Ensure index exists
            logger.error(
                f"Cannot store knowledge, index {index_name} could not be created/ensured."
            )
            return False

        document = {
            "book_id": book_id,
            "chapter_number": chapter_number,
            "extracted_at": datetime.datetime.utcnow().isoformat(),
            "knowledge": enriched_knowledge_data,  # The AI's output, enriched
        }

        try:
            self.es.index(index=index_name, document=document)
            logger.debug(
                f"Stored knowledge for book {book_id}, chapter {chapter_number} in {index_name}"
            )
            return True
        except Exception as e:
            logger.error(
                f"Failed to store knowledge for book {book_id}, chapter {chapter_number}: {e}",
                exc_info=True,
            )
            return False
