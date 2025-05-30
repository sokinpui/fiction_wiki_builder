# File: src/fwb/knowledge_extraction/pydantic_models.py

from typing import List, Optional

from pydantic import BaseModel, Field


class AIOutputDescription(BaseModel):
    """在文本中找到的关于实体或关系的文本描述。"""

    text: str = Field(..., description="描述性文本本身。")


class AIOutputRelationship(BaseModel):
    """描述源实体与目标实体之间的关系。"""

    target_entity_name: str = Field(..., description="此实体相关的目标实体的名称。")
    description: str = Field(..., description="关于关系性质的文本描述。")


class BaseAIEntity(BaseModel):
    """任何可提取实体的基础模型。"""

    name: str = Field(..., description="实体的主要名称。")
    descriptions: List[AIOutputDescription] = Field(
        default_factory=list,
        description="在当前文本中找到的关于此实体的不同文本描述列表。",
    )
    relationships: List[AIOutputRelationship] = Field(
        default_factory=list,
        description="此实体与文本中提及的其他实体所具有的关系列表。",
    )


class AICharacter(BaseAIEntity):
    """代表一个提取出的人物。"""

    aliases: List[str] = Field(
        default_factory=list, description="人物的替代名称、称号或名号。"
    )
    magic_weapon_names: List[str] = Field(
        default_factory=list,
        description="与此人物直接相关或由此人物持有的法宝、神器或重要物品的名称。如果这些法宝本身也有描述，则它们也应作为单独的法宝实体列出。",
    )


class AIMagicWeapon(BaseAIEntity):
    """代表一个提取出的法宝、奇物、灵植、重要材料或类似物品。"""

    pass  # 目前除了基础字段外，没有特定于法宝的额外字段。


class AIOrganization(BaseAIEntity):
    """代表一个提取出的组织、宗派、家族或团体。"""

    member_names: List[str] = Field(
        default_factory=list,
        description="被识别为此组织成员的人物名称。如果这些人物本身也有描述，则他们也应作为单独的人物实体列出。",
    )


class AIArea(BaseAIEntity):
    """代表一个提取出的地理区域、地点、城市或地区。"""

    organization_names_present: List[str] = Field(
        default_factory=list,
        description="已知在此区域活动或存在的组织名称。如果这些组织本身也有描述，则它们也应作为单独的组织实体列出。",
    )


class AIWorld(BaseAIEntity):
    """代表一个提取出的世界、界域、位面或维度。"""

    area_names: List[str] = Field(
        default_factory=list,
        description="构成此世界一部分的重要区域或子区域的名称。如果这些区域本身也有描述，则它们也应作为单独的区域实体列出。",
    )


class ChapterKnowledgeExtraction(BaseModel):
    """
    从书的单个章节中提取的所有相关实体及其观察到的特征和关系的综合集合。
    确保包含所有指定类型的已识别实体。
    对于关系，清楚说明目标实体的名称并描述连接。
    如果一个实体（例如法宝）在与一个人物相关的描述中被提及，并且它本身也有描述，
    则应在其人物的'magic_weapon_names'下（或其他类型的类似字段）列出其名称，并在顶层'magic_weapons'列表中为其创建一个单独的条目。
    """

    characters: Optional[List[AICharacter]] = Field(
        default_factory=list, description="章节中识别出的所有不同人物。"
    )
    magic_weapons: Optional[List[AIMagicWeapon]] = Field(
        default_factory=list,
        description="章节中识别出的所有不同法宝、奇物、灵植、修炼材料或其他重要物品。",
    )
    areas: Optional[List[AIArea]] = Field(
        default_factory=list,
        description="章节中识别出的所有不同地理区域、地点、城市或地区。",
    )
    organizations: Optional[List[AIOrganization]] = Field(
        default_factory=list,
        description="章节中识别出的所有不同组织、宗派、家族、修仙门派或其他团体。",
    )
    worlds: Optional[List[AIWorld]] = Field(
        default_factory=list,
        description="章节中识别出的所有不同世界、界域、位面或维度。",
    )
