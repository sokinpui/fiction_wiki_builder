import json
from typing import Set

from .entity_data import EntityData
from .entity_extractor import EmptyTextSourceError, EntityExtractor
from .llm.gemini import Gemini
from .wiki_graph import WikiGraph


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

        self.active_entities: Set[EntityData] = set()

        self.merge_prompt = self._get_merge_prompt("./prompt/merge_entity.txt")

        self._llm = Gemini()

    @staticmethod
    def _get_merge_prompt(path) -> str:
        """get merge prompt from file"""
        try:
            with open(path, "r") as file:
                return file.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Merge prompt file not found at {path}")

    def get_context(self, focused_entities: Set[EntityData]) -> str:
        """get context from the text"""

        if not focused_entities:
            return ""

        context = ""

        context_nodes = set()

        for node in focused_entities:
            if isinstance(node, EntityData):
                self.active_entities.add(node)
                context_nodes.update(self.graph.bfs(node.name, 1))

                for context_node in context_nodes:
                    entity_node = self.graph.get_entity_node(context_node)
                    if entity_node:
                        summary_text = "\n".join(entity_node.summary.values())
                        context += f"{entity_node.name}\n{summary_text}\n\n"

            else:
                raise ValueError("focused_entities should be a list of EntityData")

        return context

    def read_chunks(self, context: str) -> list[EntityData]:
        """read chunks and return entities list"""

        entities_str, start_chunk, end_chunk = self.reader.read(context)

        print(
            f"Extracted entities from chunks {start_chunk}-{end_chunk - 1}:\n{entities_str}"
        )

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
        """add an entity to active entities set"""
        if not isinstance(entity, EntityData):
            raise ValueError("entities should be an instance of EntityData")

        if not self.check_existing_entity(entity):
            self.active_entities.add(entity)
            print(f"Added {entity.name} to active entities")
        else:
            print(f"{entity.name} already exists in the graph, skipping addition")

    def create_new_node(self, entity: EntityData) -> None:
        """create or merge a entity node in the graph"""
        if not isinstance(entity, EntityData):
            raise ValueError("entities should be an instance of EntityData")

        if self.check_existing_entity(entity):
            self.prompt_ai_to_merge(entity)
        else:
            self.graph.add_entity_node(entity)
            self.add_active_entities(entity)

    def link_relationship(self) -> None:
        """link relationships between entities"""

        for entity in self.active_entities:
            if not self.graph.get_entity_node(entity.name):
                continue

            for node, relationship in entity.relationships:
                self.graph.add_edge(entity.name, node, relationship)
                print(
                    f"Linked {entity.name} to {node} with relationship {relationship}"
                )

    def prompt_ai_to_merge(self, entity: EntityData) -> None:
        """
        prompt AI to merge entities
        check if the entity is actually related to the existing entity
        if yes: append the summary to the existing summary
        if no: rename and create a new node
        """
        if not isinstance(entity, EntityData):
            raise ValueError("entity should be an instance of EntityData")

        # get the context of the entity that have the same name
        target_node = set()
        target_node.add(entity)
        context = self.get_context(target_node)

        new_entity_summary = "\n".join(entity.summary.values())

        prompt = self.merge_prompt.format(
            existing_entity_name=entity.name,
            existing_entity_summary=context,
            new_entity_name=entity.name,
            new_entity_summary=new_entity_summary,
        )

        # llm should only output a new name if is not the same entity actually
        # else output empty string ""
        response = self._llm.chat(prompt)

        if response == "":
            # same entity, append the summary
            print(f"Entity {entity.name} already exists, merging summaries.")
            existing_node = self.graph.get_entity_node(entity.name)
            if existing_node:
                existing_node.summary.update(entity.summary)
                self.graph.update_entity_node(existing_node)
                self.add_active_entities(existing_node)
        else:
            # different entity, create a new node
            print(f"Entity {entity.name} is different, renaming to {response}.")
            entity.name = response
            self.graph.add_entity_node(entity)
            self.add_active_entities(entity)

    def build_wiki(self) -> None:
        """build the wiki graph"""
        while True:
            # active entities from last iteration
            context = self.get_context(self.active_entities)

            categories = self.graph.get_categories()
            context += f"\n---\n\nCategories:\n{categories}\n"

            try:
                entities = self.read_chunks(context)
            except EmptyTextSourceError as e:
                print("source is empty.")
                break

            # clear active entities after context retrieved
            self.active_entities.clear()

            # new active entities is formed here
            for entity in entities:
                self.create_new_node(entity)

            self.link_relationship()


def main():

    book_id = "41814"
    graph = WikiGraph()

    builder = FictionWikiGraphBuilder(book_id, graph)

    builder.build_wiki()


if __name__ == "__main__":
    main()
