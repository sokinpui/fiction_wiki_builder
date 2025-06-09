import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingModel:
    def __init__(self):
        self.model = SentenceTransformer("BAAI/bge-m3", device="mps")

    def encode(self, texts: str | list[str]) -> np.ndarray:
        """embedding"""
        return self.model.encode(texts)
