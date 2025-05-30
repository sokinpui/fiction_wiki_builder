# File: src/fwb/knowledge_extraction/extractor.py

import logging
from typing import Any, Dict, Optional

from ..generative.gemini.gemini_model import GeminiLLMHandler  # Relative import
from .data_store import KnowledgeDataStore  # Relative import
from .pydantic_models import ChapterKnowledgeExtraction  # Relative import

logger = logging.getLogger(__name__)


class KnowledgeExtractor:
    def __init__(self, llm_handler: GeminiLLMHandler, data_store: KnowledgeDataStore):
        self.llm_handler = llm_handler
        self.data_store = data_store

    def _build_prompt(self, chapter_content: str) -> str:
        # The Pydantic model `ChapterKnowledgeExtraction` and its sub-models have
        # detailed descriptions. The LLM should use these when generating the structured output.
        # The prompt needs to guide the LLM to focus on the five entity types:
        # Character, MagicWeapon, Area, Organization, World.
        # Using Chinese prompt for better understanding with Chinese fiction.
        prompt = f"""
分析以下玄幻小说章节内容。
根据提供的JSON模式提取所有相关实体及其信息。
请重点关注以下五种主要实体类型：人物 (Character)、法宝 (MagicWeapon, 包括奇物、灵植、材料等)、地域 (Area)、势力 (Organization) 和 界面 (World)。

提取规则：
1.  实体名称：使用文本中观察到的最常用或正式的名称。
2.  描述：仅根据本章节中的信息提供简洁的描述。每一条独特的描述信息应作为一个单独的条目。
3.  关系：识别实体之间的关系。对于每个关系，请指明目标实体的名称，并描述在本章节中观察到的连接性质。
4.  特定属性：
    - 人物：包括别名和相关法宝的名称。
    - 势力：包括已知成员的名称。
    - 地域：包括存在的势力名称。
    - 界面：包括组成该界面的地域名称。
5.  完整性：努力识别这些实体类型的所有实例。如果一个实体（例如法宝）与另一个实体（例如人物）相关联，并且它本身也有描述，则应在其所属实体（例如人物）的'magic_weapon_names'（或其他类型的类似字段）下列出其名称，并在顶层列表（例如'magic_weapons'）中为其创建一个单独的条目。
6.  避免冗余：如果同一条信息（例如人物的别名）被多次提及，则只列出一次。
7.  禁止外部知识：所有提取应完全基于提供的章节文本。不要推断未明确说明的信息。
8.  空列表：如果未找到某种类型的实体，或者某个实体在本章节中没有描述/关系，请对相应的字段使用空列表 `[]`。不要省略该字段。

章节内容：
---
{chapter_content}
---
请按照 'ChapterKnowledgeExtraction' 模式定义的结构化JSON格式提供输出。
"""
        # Truncate chapter_content if it's too long to avoid overly large prompts,
        # though Gemini models have large context windows.
        # Adjust 100000 as needed, or use token counting.
        return prompt

    def _enrich_knowledge_data(
        self, ai_output: ChapterKnowledgeExtraction, chapter_number: int
    ) -> Dict[str, Any]:
        """
        Enriches the AI-extracted data by adding chapter numbers to descriptions and relationships.
        Converts Pydantic model to dict for ES storage.
        """
        enriched_data = ai_output.model_dump(
            exclude_none=True
        )  # Use exclude_none to keep output cleaner if lists are empty

        entity_categories = [
            "characters",
            "magic_weapons",
            "areas",
            "organizations",
            "worlds",
        ]

        for category_key in entity_categories:
            entities = enriched_data.get(category_key, [])
            if not entities:  # handles None or empty list
                enriched_data[category_key] = []  # Ensure key exists with empty list
                continue

            for entity in entities:
                # Enrich descriptions
                new_descriptions = []
                for desc_obj in entity.get("descriptions", []):
                    new_descriptions.append(
                        {"chapter": chapter_number, "text": desc_obj.get("text", "")}
                    )
                entity["descriptions"] = new_descriptions

                # Enrich relationships
                new_relationships = []
                for rel_obj in entity.get("relationships", []):
                    new_relationships.append(
                        {
                            "target_entity_name": rel_obj.get("target_entity_name", ""),
                            "description": {
                                "chapter": chapter_number,
                                "text": rel_obj.get(
                                    "description", ""
                                ),  # Relationship description was a simple string from AI
                            },
                        }
                    )
                entity["relationships"] = new_relationships
        return enriched_data

    def process_chapter(self, book_id: str, chapter_data: Dict[str, Any]) -> bool:
        chapter_number = chapter_data.get("chapter_number")
        chapter_content = chapter_data.get("chapter_content")

        if chapter_number is None or not chapter_content:
            logger.warning(
                f"Missing chapter_number or content for a chapter in book {book_id}. Skipping."
            )
            return False

        logger.info(f"Processing Book ID: {book_id}, Chapter: {chapter_number}")

        prompt = self._build_prompt(chapter_content)

        try:
            # Use the ChapterKnowledgeExtraction model as the schema for structured output
            extracted_data_model = self.llm_handler.generate(
                prompt, schema=ChapterKnowledgeExtraction
            )

            if not extracted_data_model:
                logger.error(
                    f"AI returned no data for book {book_id}, chapter {chapter_number}."
                )
                return False

            if not isinstance(extracted_data_model, ChapterKnowledgeExtraction):
                logger.error(
                    f"AI output for book {book_id}, chapter {chapter_number} is not of type ChapterKnowledgeExtraction. Type: {type(extracted_data_model)}. Output: {extracted_data_model}"
                )
                # Potentially log the actual output if it's small enough or relevant parts
                return False

            logger.info(
                f"Successfully extracted knowledge for book {book_id}, chapter {chapter_number}."
            )

            enriched_data = self._enrich_knowledge_data(
                extracted_data_model, chapter_number
            )

            return self.data_store.store_knowledge(
                book_id, chapter_number, enriched_data
            )

        except Exception as e:
            logger.error(
                f"Error processing chapter {chapter_number} of book {book_id}: {e}",
                exc_info=True,
            )
            return False

    def process_book(self, book_id: str):
        logger.info(f"Starting knowledge extraction for Book ID: {book_id}")

        if not self.data_store.create_knowledge_index_if_not_exists(book_id):
            logger.error(
                f"Failed to ensure knowledge index for book {book_id}. Aborting."
            )
            return

        chapters_processed_count = 0
        chapters_succeeded_count = 0

        for chapter_data in self.data_store.get_chapters(book_id):
            chapters_processed_count += 1
            if self.process_chapter(book_id, chapter_data):
                chapters_succeeded_count += 1
            # Consider adding a delay here if rate limits are hit frequently
            # despite the rate_tracker in GeminiLLMHandler.
            # time.sleep(1)

        logger.info(f"Finished processing Book ID: {book_id}.")
        logger.info(f"Total chapters encountered: {chapters_processed_count}")
        logger.info(
            f"Successfully processed and stored knowledge for: {chapters_succeeded_count} chapters."
        )
