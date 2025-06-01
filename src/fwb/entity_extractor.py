from elasticsearch import Elasticsearch

from .llm.gemini import Gemini


class EntityExtractor:
    def __init__(self, book_id, cuhnk_length: int = 1):
        self.model: Gemini = Gemini()

        self.book_id: str = book_id

        self._source_index: str = f"book_{self.book_id}"

        self._progress_index: str = f"progress_{self.book_id}"

        self._output_index: str = f"entities_{self.book_id}"

        self.prompt: str = self._get_prompt("./prompt/entity_extraction.txt")

        self.chunk_length: int = cuhnk_length

        self._es = Elasticsearch(hosts=["http://localhost:9200"])

    def extract_entities(self, text: str) -> str:
        """
        prompts to AI to extract entities from the given text.

        return a json string with the extracted entities.
        """

        context = ""
        source = context + text + self.prompt
        raw_output = self.model.chat(source)
        response = self.model.parse_response(raw_output)

        return response

    @staticmethod
    def _get_prompt(file_path: str) -> str:
        """
        Reads the prompt from a file.
        """
        with open(file_path, "r") as file:
            return file.read()

    def get_chunk(self, book_id) -> str:
        """
        Get the chunk of text to process.
        """
        chunk = ""
        chunk_id = str(self.get_chunk_id())
        for i in range(1, self.chunk_length + 1):
            pass
            # try:
            #     response = self._es.get(index="chunks", id=f"{id}-{i}")
            #     return response["_source"]["text"]
            # except Exception as e:
            #     print(f"Error getting chunk {id}-{i}: {e}")
            ## get the chunk from elasticsearch

    def get_chunk_id(self) -> int:
        """
        Get the current chunk ID from Elasticsearch.
        """
        try:
            response = self._es.get(index=self._progress_index, id="current")
            return response["_source"]["id"]
        except Exception as e:
            print(f"Error getting chunk ID: {e}")
            return 0

    def reset_chunk_id(self) -> None:
        """
        Reset the chunk ID in Elasticsearch.
        """
        try:
            self._es.index(index=self._progress_index, id="current", body={"id": 1})
        except Exception as e:
            print(f"Error resetting chunk ID: {e}")

    def set_chunk_id(self, id: int) -> None:
        """
        Set the current chunk ID in Elasticsearch.
        """
        try:
            self._es.index(index=self._progress_index, id="current", body={"id": id})
        except Exception as e:
            print(f"Error setting chunk ID: {e}")

    def save_entities(self, entities: str) -> None:
        """
        Save the extracted entities to Elasticsearch.
        """
        # try:
        #     self._es.index(index=self._output_index, id=self.get_chunk_id(), body={"entities": entities})
        # except Exception as e:
        #     print(f"Error saving entities: {e}")
        pass
