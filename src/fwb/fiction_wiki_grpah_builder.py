import json
import logging
import sys
from typing import List

from .entity_data import EntityData
from .entity_extractor import EmptyTextSourceError, EntityExtractor
from .llm.gemini import Gemini
from .wiki_graph import WikiGraph

logging.basicConfig(level=logging.INFO)

CONTEXT_SIZE = 10  # Number of recent summaries to include in context


class FictionWikiGraphBuilder:
    """
    wiki builder for fiction
    assume no mixed or similar ideas should present in the source
    assume all characters are unique
    """

    def __init__(
        self,
        book_id: str,
        graph: WikiGraph,
    ):
        self.book_id = book_id
        self.graph = graph
        self.reader = EntityExtractor(book_id)

        self.active_entities: List[EntityData] = []

        self._llm = Gemini()

    def get_context(self, focused_entities: List[EntityData]) -> str:
        """get context from the text"""

        if not focused_entities:
            return ""

        context = ""

        for node in focused_entities:
            if isinstance(node, EntityData):
                entity_node = self.graph.get_entity_node(node.name)
                if entity_node:
                    summary_items = entity_node.summary.items()

                    sorted_summary_items = sorted(
                        summary_items,
                        key=lambda item: int(item[0].lstrip("c").split("-")[0]),
                    )

                    recent_summary_texts = [
                        text for key, text in sorted_summary_items[-CONTEXT_SIZE:]
                    ]

                    summary_text = "\n\n".join(recent_summary_texts)
                    context += f"{entity_node.name}\n{summary_text}\n\n\n"

            else:
                raise ValueError("focused_entities should be a list of EntityData")

        print(f"Context:\n{context[:500]}...")
        return context

    def read_chunks(self, context: str) -> list[EntityData]:
        """read chunks and return entities list"""

        entities_str, start_chunk, end_chunk = self.reader.read(context)

        if not entities_str:
            return []

        try:
            entities_json = json.loads(entities_str)

            # Chapter key format: 'c1' for chunk 1, 'c2-3' for chunks 2 to 3.
            chunk_range_end = end_chunk - 1
            chunk_range = f"c{start_chunk}"
            if chunk_range_end > start_chunk:
                chunk_range += f"-{chunk_range_end}"

            result_entities = []
            for entity_payload in entities_json:
                # The AI returns summary as a string. We pop it and handle it separately.
                new_summary_text = entity_payload.pop("summary", "")

                # Create the EntityData object without the summary first
                entity = EntityData(**entity_payload)

                # Now, add the summary with the chapter key
                if new_summary_text:
                    entity.summary[chunk_range] = new_summary_text

                result_entities.append(entity)

            return result_entities

        except json.JSONDecodeError as e:
            print(f"Error decoding JSON: {e}")
            return []

    def check_existing_entity(self, entity: EntityData) -> bool:
        """check if the entity already exists in the graph"""
        existing_node = self.graph.get_entity_node(entity.name)
        if existing_node:
            return True
        return False

    def add_active_entities(self, entity: EntityData) -> None:
        """Add an entity to active entities list, ensuring uniqueness by name."""
        if not isinstance(entity, EntityData):
            raise ValueError("entities should be an instance of EntityData")

        if not any(e.name == entity.name for e in self.active_entities):
            self.active_entities.append(entity)
            print(f"Added {entity.name} to active entities.")
        else:
            print(f"{entity.name} is already active, skipping addition.")

    def create_or_update_node(self, entity: EntityData) -> None:
        """create or merge a entity node in the graph"""
        if not isinstance(entity, EntityData):
            raise ValueError("entities should be an instance of EntityData")

        if self.check_existing_entity(entity):
            existing_node = self.graph.get_entity_node(entity.name)
            existing_node.summary.update(entity.summary)
            self.graph.update_entity_node(existing_node)
            self.add_active_entities(existing_node)
        else:
            self.graph.add_entity_node(entity)
            self.add_active_entities(entity)

    def link_relationship(self) -> None:
        """link relationships between entities"""

        for entity in self.active_entities:
            if not self.graph.get_entity_node(entity.name):
                continue

            for node, relationship in entity.relationships.items():
                parsed_rel = (
                    relationship.replace(",", "_")
                    .replace(" ", "_")
                    .replace(";", "_")
                    .replace("/", "_")
                    .replace("&", "_")
                    .replace("\\", "_")
                    .replace("、", "_")
                )
                self.graph.add_edge(entity.name, node, parsed_rel)
                print(
                    f"Linked {entity.name} to {node} with relationship {relationship}"
                )

    def build_wiki(self) -> None:
        """build the wiki graph"""
        while True:
            # active entities from last iteration
            context = self.get_context(self.active_entities)

            categories = self.graph.get_categories()
            context += f"\n---\n\nCategories:\n{categories}\n"

            while True:
                try:
                    entities = self.read_chunks(context)
                    if len(entities) == 0:
                        print("No entities found in the current context.")
                        print("Ending the build process.")
                        print("something went wrong, please check the source.")
                        sys.exit(1)
                    break
                except EmptyTextSourceError as e:
                    print("source is empty.")
                    sys.exit(1)
                except json.JSONDecodeError as e:
                    print(f"Error decoding JSON: {e}")
                    continue

            # clear active entities after context retrieved
            self.active_entities = []

            # new active entities is formed here
            for entity in entities:
                self.create_or_update_node(entity)

            try:
                self.link_relationship()
            except Exception as e:
                logging.error(f"Error linking relationships: {e}")
                continue

            progress = self.reader.get_progress()
            self.reader.save_progress(progress + 1)


def main():

    book_id = "46029"
    graph = WikiGraph()

    builder = FictionWikiGraphBuilder(book_id, graph)
    builder.build_wiki()


if __name__ == "__main__":
    main()
