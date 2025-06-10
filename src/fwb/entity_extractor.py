from .llm.gemini import Gemini
from .progress_buf import ProgressBuffer


class EmptyTextSourceError(Exception):
    """Exception raised when the text source is empty."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


class EntityExtractor:
    """extract entities from book"""

    def __init__(self, book_id, cuhnk_length: int = 1):
        self.model: Gemini = Gemini()
        self.extract_prompt: str = self._get_prompt("./prompt/entity_extraction.txt")

        # book to read
        self.book_id: str = book_id

        # how many chapters to read at once
        self.chunk_length: int = cuhnk_length

        # init elasticsearch client
        self.buffer = ProgressBuffer()

    def extract_entities(self, context: str, text: str) -> str:
        """
        prompts to AI to extract entities from the given text.

        return a json string with the extracted entities.
        """

        prompt = self.extract_prompt.format(
            context=context,
            text=text,
        )

        raw_output = self.model.chat(prompt)
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
        return self.buffer.get_progress(self.book_id)

    def save_progress(self, progress: int) -> None:
        """
        Sets the progress of reading aka chapter number
        """
        self.buffer.save_progress(self.book_id, progress)

    def reset_progress(self) -> None:
        """
        Resets the progress of reading aka chapter number
        """
        self.buffer.reset_progress(self.book_id)

    def read(self, context: str) -> str:
        """
        Reads the book in chunks and extracts entities from each chunk.
        """
        text = ""

        start_chunk_id = self.get_progress()

        for i in range(1, self.chunk_length + 1):

            progress = self.get_progress()

            new_source = self.buffer.get_source_chunk(self.book_id, progress)
            if new_source == "":
                raise EmptyTextSourceError(
                    f"Empty text source for book {self.book_id} at chapter {progress}"
                )

            text += new_source

            self.buffer.save_progress(self.book_id, progress + 1)

        response = self.extract_entities(context, text)

        end_chunk_id = self.get_progress()

        self.buffer.save_entities_to_buffer(
            self.book_id, response, start_chunk_id, end_chunk_id
        )

        return response


def main():
    book_id = "41814"

    extractor = EntityExtractor(book_id, cuhnk_length=1)
    context = "This is a test context for entity extraction."
    response = extractor.read(context)
    print("Extracted Entities:", response)


if __name__ == "__main__":
    main()
