from collections import deque

from neo4j import GraphDatabase

from .entity_data import EntityData

uri = "neo4j://localhost:7687"
username = "neo4j"
password = "P@ssw0rd"


class WikiGraph:
    """operation related to graph storage"""

    def __init__(self):
        """Initialize the GraphStorage instance."""
        self.graph = GraphDatabase.driver(
            "neo4j://localhost:7687", auth=(username, password)
        )

        self.graph.verify_connectivity()

    def close(self) -> None:
        """Close the connection to the Neo4j database."""
        if self.graph:
            self.graph.close()

    def add_entity_node(self, entity_data: EntityData) -> int:
        """Add an entity node to the graph"""
        with self.graph.session() as session:
            query = """
            MERGE (n:Entity {name: $name})
            SET n.category = $category,
                n.summary = $summary
            RETURN elementid(n)
            """
            result = session.run(
                query,
                name=entity_data.name,
                category=entity_data.category,
                summary=entity_data.summary,
            )
            node_id = result.single()[0]
            return node_id

    def update_entity_node(self, entity_data: EntityData) -> None:
        """Update an existing entity node."""
        with self.graph.session() as session:
            query = """
            MATCH (n:Entity {name: $name})
            SET n.category = $category,
                n.summary = $summary
            """
            session.run(
                query,
                name=entity_data.name,
                category=entity_data.category,
                summary=entity_data.summary,
            )

    def create_alias(self, node_a: str, node_b: str) -> None:
        """node B will point to node A as an alias."""

        with self.graph.session() as session:
            query = """
            MATCH (a:Entity {name: $node_a}), (b:Entity {name: $node_b})
            MERGE (b)-[:ALIAS]->(a)
            """
            session.run(query, node_a=node_a, node_b=node_b)

    def get_entity_node(self, name: str) -> EntityData | None:
        """Retrieve a node by its name, resolving to any aliases.
        Returns an EntityData object or None if not found."""
        with self.graph.session() as session:
            # Query first resolves 'name' to its canonical node (if 'name' is an alias)
            # then returns properties of that canonical node.
            query = """
            MATCH (n_input:Entity {name: $name})
            OPTIONAL MATCH (n_input)-[:ALIAS]->(aliased_to:Entity)
            WITH CASE
                WHEN aliased_to IS NOT NULL THEN aliased_to
                ELSE n_input
            END AS resolved_node
            RETURN resolved_node.name AS name,
                   resolved_node.category AS category,
                   resolved_node.summary AS summary
            """
            result = session.run(query, name=name)
            record = result.single()
            if record:
                return EntityData(
                    name=record["name"],
                    category=record["category"],
                    summary=record["summary"],
                )
            return None

    def delete_node(self, name: str) -> None:
        """
        Delete a node by its name.
        remove all aliases associated with the node
        """
        with self.graph.session() as session:
            query = """
            MATCH (n:Entity {name: $name})
            DETACH DELETE n
            """
            session.run(query, name=name)

    def clear_all_data(self) -> None:
        """Deletes all nodes and relationships. USE WITH CAUTION."""
        with self.graph.session() as session:
            query = "MATCH (n) DETACH DELETE n"
            session.run(query)
            print("All data cleared from the graph.")

    def add_edge(self, source: str, target: str, edge_type: str) -> None:
        """Add an edge between two nodes."""
        with self.graph.session() as session:
            query = (
                """
            MATCH (a:Entity {name: $source}), (b:Entity {name: $target})
            MERGE (a)-[r:%s]->(b)
            RETURN r
            """
                % edge_type
            )
            session.run(query, source=source, target=target)

    def get_edges_outgoing(self, node_name: str) -> list[tuple[str, str]]:
        """Get all outgoing edges from a node."""
        with self.graph.session() as session:
            query = """
            MATCH (n:Entity {name: $node_name})-[r]->(m)
            RETURN type(r) AS edge_type, m.name AS target_node
            """
            result = session.run(query, node_name=node_name)
            return [(record["edge_type"], record["target_node"]) for record in result]

    def get_edges_in(self, node_name: str) -> list[tuple[str, str]]:
        """Get all incoming edges to a node."""
        with self.graph.session() as session:
            query = """
            MATCH (m)-[r]->(n:Entity {name: $node_name})
            RETURN type(r) AS edge_type, m.name AS source_node
            """
            result = session.run(query, node_name=node_name)
            return [(record["edge_type"], record["source_node"]) for record in result]

    def get_edge_atob(self, node_a: str, node_b: str) -> str | None:
        """get the edge attribute from ndoe A to node B"""
        with self.graph.session() as session:
            query = """
            MATCH (a:Entity {name: $node_a})-[r]->(b:Entity {name: $node_b})
            RETURN type(r) AS edge_type
            """
            result = session.run(query, node_a=node_a, node_b=node_b)
            record = result.single()
            if record:
                return record["edge_type"]
            return None

    def delete_edge(self, source: str, target: str) -> None:
        """Delete an edge between two nodes."""
        with self.graph.session() as session:
            query = """
            MATCH (a:Entity {name: $source})-[r]->(b:Entity {name: $target})
            DELETE r
            """
            session.run(query, source=source, target=target)

    def update_edge(self, source: str, target: str, edge_type: str) -> None:
        """Update an existing edge between two nodes."""
        self.delete_edge(source, target)
        self.add_edge(source, target, edge_type)

    def is_edge_exists(self, source: str, target: str) -> bool:
        """Check if an edge exists between two nodes."""
        with self.graph.session() as session:
            query = """
            MATCH (a:Entity {name: $source})-[r]->(b:Entity {name: $target})
            RETURN COUNT(r) > 0 AS edge_exists
            """
            result = session.run(query, source=source, target=target)
            record = result.single()

            return record["edge_exists"] if record else False

    def bfs(self, start_node: str, max_depth: int) -> list[str]:
        """BFS, return including the start node"""
        if not self.get_entity_node(start_node):
            print(f"Start node '{start_node}' not found or is not an Entity.")
            return []

        queue = deque([(start_node, 0)])
        visited = {start_node}

        result = []

        while queue:
            current_node, depth = queue.popleft()
            result.append(current_node)

            if depth < max_depth:
                edges = self.get_edges_outgoing(current_node)
                for edge_type, target_node in edges:
                    if target_node not in visited:
                        visited.add(target_node)
                        queue.append((target_node, depth + 1))

        return result

    def get_categories(self) -> list[str]:
        """Get all unique categories from the graph using a single, robust query."""
        with self.graph.session() as session:
            query = """
            OPTIONAL MATCH (n:Entity)
            WHERE n.category IS NOT NULL
            RETURN collect(DISTINCT n.category) AS categories
            """
            result = session.run(query).single()

            return result["categories"] if result else []
