from pydantic import BaseModel, Field


class EntityData(BaseModel):
    """
    Data format for an entity
    """

    name: str = Field(..., description="Name of the entity")
    # summary: list[str] = Field(
    #     default_factory=list,
    #     description="List of historical summaries for the entity",
    # )

    # use string for easier serialization
    summary: str = Field(
        description="historical summaries for the entity",
    )

    categories: str
    relationships: dict[str, str] = Field(
        default_factory=dict,
        description="List of relationships with other entities",
    )

    @classmethod
    def from_node(cls, node):  # node is a neo4j.graph.Node
        return cls(
            name=node.get("name"),
            categories=node.get("categories", []),
            summary=node.get("historical_summary", ""),
        )
