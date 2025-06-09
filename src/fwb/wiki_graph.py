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

    def close(self):
        """Close the connection to the Neo4j database."""
        if self.graph:
            self.graph.close()

    def add_entity_node(self, entity_data: EntityData) -> int:
        """Add an entity node to the graph"""
        with self.graph.session() as session:
            query = """
            MERGE (n:Entity {name: $name})
            SET n.categories = $categories,
                n.summary = $summary
            RETURN elementid(n)
            """
            result = session.run(
                query,
                name=entity_data.name,
                categories=entity_data.categories,
                summary=entity_data.summary,
            )
            node_id = result.single()[0]
            return node_id

    def update_entity_node(self, entity_data: EntityData):
        """Update an existing entity node."""
        with self.graph.session() as session:
            query = """
            MATCH (n:Entity {name: $name})
            SET n.categories = $categories,
                n.summary = $summary
            """
            session.run(
                query,
                name=entity_data.name,
                categories=entity_data.categories,
                summary=entity_data.summary,
            )

    def create_alias(self, node_a: str, node_b: str):
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
                   resolved_node.categories AS categories,
                   resolved_node.summary AS summary
            """
            result = session.run(query, name=name)
            record = result.single()
            if record:
                return EntityData(
                    name=record["name"],
                    categories=record["categories"],
                    summary=record["summary"],
                )
            return None

    def delete_node(self, name: str):
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

    def clear_all_data(self):
        """Deletes all nodes and relationships. USE WITH CAUTION."""
        with self.graph.session() as session:
            query = "MATCH (n) DETACH DELETE n"
            session.run(query)
            print("All data cleared from the graph.")

    def add_edge(self, source: str, target: str, edge_type: str):
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

    def update_edge(self, source: str, target: str, edge_type: str):
        """Update an existing edge between two nodes."""
        with self.graph.session() as session:
            query = (
                """
            MATCH (a:Entity {name: $source})-[r:%s]->(b:Entity {name: $target})
            SET r.type = $edge_type
            RETURN r
            """
                % edge_type
            )
            session.run(query, source=source, target=target, edge_type=edge_type)

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
        """bfs with deep limit, return list of names"""
        with self.graph.session() as session:
            query = """
            MATCH (n_input:Entity {name: $start_node_param})
            OPTIONAL MATCH (n_input)-[:ALIAS]->(aliased_to:Entity)
            WITH CASE
                WHEN aliased_to IS NOT NULL THEN aliased_to
                ELSE n_input
            END AS resolved_s_node
            WHERE resolved_s_node IS NOT NULL

            CALL {
                WITH resolved_s_node
                MATCH path = (resolved_s_node)-[rels*0..$max_depth_param]->(target_node:Entity)
                WHERE ALL(r IN rels WHERE type(r) <> 'ALIAS')
                UNWIND nodes(path) AS bfs_node
                WITH DISTINCT bfs_node
                RETURN COLLECT(bfs_node.name) AS node_names_list
            }
            RETURN node_names_list
            """
            params = {
                "start_node_param": start_node,
                "max_depth_param": max_depth,
            }
            result = session.run(query, params)
            record = result.single()

            if record and record["node_names_list"] is not None:
                return record["node_names_list"]
            return []
