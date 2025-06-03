from .graph_storage import GraphStorage
from .vector_storage import VecotrStorage


class WikiGraph:
    """
    a directed graph
    use graph storage as the graph
    code can be stop at any time and continue later
    graph as well, graph is retrieved from graph db at runtime
    """

    def __init__(self):
        """
        :param graph: a directed graph
        """
        self.graph = GraphStorage()
        self.vector_storage = VecotrStorage()
