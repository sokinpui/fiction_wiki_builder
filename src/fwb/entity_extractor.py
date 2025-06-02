from .es_storage import ElasticsearchStore
from .llm.gemini import Gemini


class EntityExtractor:
    def __init__(self, book_id, cuhnk_length: int = 1):
        # init llm model
        self.model: Gemini = Gemini()
        self.extract_prompt: str = self._get_prompt("./prompt/entity_extraction.txt")

        # book to read
        self.book_id: str = book_id

        # how many chapters to read at once
        self.chunk_length: int = cuhnk_length

        # init elasticsearch client
        self._es = ElasticsearchStore()

    def extract_entities(self, text: str) -> str:
        """
        prompts to AI to extract entities from the given text.

        return a json string with the extracted entities.
        """

        context = ""
        source = context + text + self.extract_prompt

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

    def get_progress(self) -> int:
        """
        Retrieves the progress of reading aka chapter number
        """
        return self._es.get_progress(self.book_id)

    def save_progress(self, progress: int) -> None:
        """
        Sets the progress of reading aka chapter number
        """
        self._es.save_progress(self.book_id, progress)

    def reset_progress(self) -> None:
        """
        Resets the progress of reading aka chapter number
        """
        self._es.reset_progress(self.book_id)

    def read_book(self) -> None:
        """
        Reads the book in chunks and extracts entities from each chunk.
        """
        text = ""
        for i in range(1, self.chunk_length + 1):
            progress = self.get_progress()
            text += self._es.get_source_chunk(self.book_id, progress)
            self._es.save_progress(self.book_id, progress + 1)

        response = self.extract_entities(text)

        self._es.save_entities_to_buffer(self.book_id, response)
