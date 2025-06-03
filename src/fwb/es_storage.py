# fwb/elasticsearch_store.py
import json
import uuid

from elasticsearch import Elasticsearch, NotFoundError


class ESBuffer:
    """
    operation related to Elasticsearch storage for book entities and progress.
    """

    def __init__(self, es_hosts: list[str] = ["http://localhost:9200"]):
        self._es = Elasticsearch(hosts=es_hosts)

    def _get_source_index(self, book_id: str) -> str:
        """Get the index name for the book source."""
        return f"book_{book_id}"

    def _get_progress_index(self, book_id: str) -> str:
        """Get the index name for the book progress."""
        return f"progress_{book_id}"

    def _get_output_index(self, book_id: str) -> str:
        """Get the index name for the entities output."""
        return f"entities_{book_id}"

    def _get_buffer_index(self, book_id: str) -> str:
        """Get the index name for the book buffer."""
        return f"buffer_{book_id}"

    def get_source_chunk(self, book_id: str, chunk_id: int) -> str:
        """Retrieve a specific chunk of the book source by book ID and chunk ID."""
        index = self._get_source_index(book_id)

        query = {"query": {"term": {"chapter_number": chunk_id}}}
        try:
            response = self._es.search(index=index, body=query)
            hits = response.get("hits", {}).get("hits", [])
            if hits:
                return hits[0].get("_source", {}).get("chapter_content", "")
            else:
                return ""
        except NotFoundError:
            return ""

    ## Save and retrieve reading progress for a book
    def save_progress(self, book_id: str, progress: int) -> None:
        """Save the reading progress for a book."""
        index = self._get_progress_index(book_id)
        doc = {"doc": {"book_id": book_id, "progress": progress}, "doc_as_upsert": True}
        self._es.index(index=index, body=doc)

    def get_progress(self, book_id: str) -> int:
        """Retrieve the reading progress for a book."""
        index = self._get_progress_index(book_id)

        query = {"query": {"term": {"book_id": book_id}}}
        try:
            response = self._es.search(index=index, body=query)
            hits = response.get("hits", {}).get("hits", [])
            if hits:
                return hits[0].get("_source", {}).get("progress", 0)
            else:
                return 0
        except NotFoundError:
            return 0

    def reset_progress(self, book_id: str) -> None:
        """Reset the reading progress for a book."""
        index = self._get_progress_index(book_id)
        self._es.delete_by_query(
            index=index, body={"query": {"term": {"book_id": book_id}}}
        )

    ## Save and retrieve entities in the buffer for a book
    def save_entities_to_buffer(
        self, book_id: str, entities: str, starting_chunk_id: int, end_chunk_id: int
    ) -> None:
        """Save entities to the buffer for a book."""
        index = self._get_buffer_index(book_id)
        entities = json.loads(entities) if isinstance(entities, str) else entities
        for entity in entities:
            entity_id = str(uuid.uuid4())
            doc = {
                "book_id": book_id,
                "entity": entity,
                "entity_id": entity_id,
                "starting_chunk_id": starting_chunk_id,
                "end_chunk_id": end_chunk_id,
            }
            self._es.index(index=index, body=doc)

    def get_entities_from_buffer(self, book_id: str) -> list[dict]:
        """Retrieve entities from the buffer for a book."""
        index = self._get_buffer_index(book_id)

        query = {"query": {"term": {"book_id": book_id}}}
        try:
            response = self._es.search(index=index, body=query)
            hits = response.get("hits", {}).get("hits", [])
            return [hit.get("_source", {}) for hit in hits]
        except NotFoundError:
            return []

    def clear_buffer(self, book_id: str) -> None:
        """Clear the buffer for a book."""
        index = self._get_buffer_index(book_id)
        self._es.delete_by_query(
            index=index, body={"query": {"term": {"book_id": book_id}}}
        )

    def get_book_length(self, book_id: str) -> int:
        """Get the number of chunks in the book source."""
        index = self._get_source_index(book_id)

        query = {"query": {"match_all": {}}}
        try:
            response = self._es.count(index=index, body=query)
            return response.get("count", 0)
        except NotFoundError:
            return 0
