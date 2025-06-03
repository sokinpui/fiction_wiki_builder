from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    def __init__(self):
        self.model = SentenceTransformer("BAAI/bge-m3", device="mps")

    def encode(self, texts: str | list[str]) -> list[float] | list[list[float]]:
        """embedding"""
        return self.model.encode(texts).tolist()
