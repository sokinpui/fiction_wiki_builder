import logging

from elasticsearch import Elasticsearch
from llm.gemini import Gemini


class EntityExtractor:
    def __init__(self, book_id: str):

        self.es = Elasticsearch(hosts=["http://localhost:9200"])

        self.extract_entity_prompt = self._load_extraction_prompts(
            "prompt/entity_extraction.txt"
        )

        self.model = Gemini()
        self.book_id = book_id
        self.es_index = f"book_{self.book_id}"
        self.current_chapter_id = 0

    @staticmethod
    def _load_extraction_prompts(file_path):
        with open(file_path, "r") as file:
            return file.read()

    def extract_entities(self, text) -> str:
        """
        Extract entities from the given text using the prompts.
        """

        response = self.model.chat(text + self.extract_entity_prompt)

        parsed_response = self.model.parse_response(response)

        return parsed_response

    def insert_to_es(self, index_name: str, document: dict):
        """
        Insert a document into the specified Elasticsearch indexand gemini llm.
        """
        try:
            self.es.index(index=index_name, body=document)
            print(f"Document inserted into {index_name} successfully.")
        except Exception as e:
            print(f"Error inserting document into {index_name}: {e}")

    def process_data(self):
        pass

    def read_chapter(self, chapter_id: int) -> str:
        """
        Reads a chapter from the book by its ID and returns the text content.

        Args:
            chapter_id: The integer ID of the chapter (e.g., 1 for chapter 1).

        Returns:
            The chapter content as a string, or an empty string if not found
            or an error occurs.
        """
        self.current_chapter_id = chapter_id
        return self.get_chapter_text(chapter_id)

    def get_book_length(self) -> int:
        """
        Retrieves the total number of chapters in the book from Elasticsearch.

        Returns:
            The total number of chapters as an integer, or 0 if not found
            or an error occurs.
        """
        query = {
            "query": {"match_all": {}},
            "size": 0,
            "aggs": {"total_chapters": {"cardinality": {"field": "chapter_number"}}},
        }

        try:
            response = self.es.search(index=self.es_index, body=query)
            return response["aggregations"]["total_chapters"]["value"]

        except Exception as e:
            logging.error(
                f"Error retrieving book length for {self.book_id} (index {self.es_index}): {e}"
            )
            return 0

    def get_chapter_text(self, chapter_id: int) -> str:
        """
        Retrieves the text content of a specific chapter from Elasticsearch.

        Args:
            chapter_id: The integer ID of the chapter (e.g., 1 for chapter 1).

        Returns:
            The chapter content as a string, or an empty string if not found
            or an error occurs.
        """
        query = {
            "query": {
                "term": {
                    # Field name from ingest_books.py mapping
                    "chapter_number": chapter_id
                }
            }
        }

        try:
            response = self.es.search(index=self.es_index, body=query)

            return (
                response["hits"]["hits"][0]["_source"]["chapter_content"]
                if response["hits"]["hits"]
                else ""
            )

        except Exception as e:
            logging.error(
                f"Error retrieving chapter {chapter_id} from book {self.book_id} (index {self.es_index}): {e}"
            )
            return ""


def main():
    # Example usage of EntityExtractor
    book_id = "46029"
    extractor = EntityExtractor(book_id)
    chapter_id = 1
    print(f"Total chapters in book {book_id}: {extractor.get_book_length()}")
    pass


if __name__ == "__main__":
    main()
