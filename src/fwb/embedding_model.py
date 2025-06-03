from sentence_transformers import SentenceTransformer


class Vectorizer:
    def __init__(self, model):
        self.model = model

    def embed(self, text):
        return self.model.encode(text, convert_to_tensor=True)

    def embed_batch(self, texts):
        return self.model.encode(texts, convert_to_tensor=True)
