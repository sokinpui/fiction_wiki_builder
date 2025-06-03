from pymilvus import (
    MilvusClient,
)
from pymilvus.model.hybrid import BGEM3EmbeddingFunction

NODE_COLLECTION = "node_collection"

EDGE_COLLECTION = "edge_collection"


class VecotrStorage:
    """
    operation related to vector storage.
    """

    def __init__(self):
        """initialize the Milvus"""
        self.node_store = MilvusClient("milvus_node.db")
        self.edge_store = MilvusClient("milvus_edge.db")

        # create collections
        self._ensure_collection_exists()

        # initialize embedding function
        self.embedding_function = BGEM3EmbeddingFunction(
            model_name="BAAI/bge-m3", device="mps", use_fp16=False
        )

    def _ensure_collection_exists(self) -> None:
        """Ensure the collection exists."""
        if not self.node_store.has_collection(collection_name=NODE_COLLECTION):
            self.node_store.create_collection(
                collection_name=NODE_COLLECTION, dimension=1024
            )

        if not self.edge_store.has_collection(collection_name=EDGE_COLLECTION):
            self.edge_store.create_collection(
                collection_name=EDGE_COLLECTION, dimension=1024
            )

    def _vectorize_docs(self, docs: str) -> list[list[float]]:
        """Convert documents to embeddings."""
        return self.embedding_function.encode_documents(docs)
