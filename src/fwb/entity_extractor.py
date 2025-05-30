from elasticsearch import Elasticsearch

from .llm.gemini import Gemini


class EntityExtractor:
    def __init__(self):

        self.es = Elasticsearch(hosts=["http://localhost:9200"])

        self.extract_entity_prompt = self._load_extraction_prompts(
            "prompt/entity_extraction.txt"
        )
        self.model = Gemini()

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
