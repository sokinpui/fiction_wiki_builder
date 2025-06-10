from pydantic import BaseModel, Field


class EntityData(BaseModel):
    """
    Data format for an entity
    """

    name: str = Field(..., description="Name of the entity")

    summary: dict[str, str] = Field(
        default_factory=dict,
        description="Historical summaries for the entity, mapping chapter range to summary text.",
    )

    category: str
    relationships: dict[str, str] = Field(
        default_factory=dict,
        description="List of relationships with other entities",
    )
