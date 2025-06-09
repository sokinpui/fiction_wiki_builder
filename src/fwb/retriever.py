from .entity_data import EntityData
from .wiki_graph import WikiGraph


class Retriever:
    """retrieve from graph"""

    def __init__(self, graph: WikiGraph):
        self.graph = graph

    def retrieve(self, node_name, deep=1) -> str:
        """
        retrieve from graph
        run BFS with deep on given node,
        """
        if deep < 1:
            raise ValueError("deep must be greater than or equal to 1")

        nodes = self.graph.bfs(node_name, deep)
        entity_list = [self.graph.get_entity_node(node) for node in nodes]

        retrieve_context = [
            f"{entity.name}:\n{entity.summary}\n\n"
            for entity in entity_list
            if isinstance(entity, EntityData)
        ]

        return "".join(retrieve_context)
