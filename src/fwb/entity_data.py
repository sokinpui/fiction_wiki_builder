from pydantic import BaseModel, Field


class EntityData(BaseModel):
    """
    Data format for an entity
    """

    name: str = Field(..., description="Name of the entity")
    historial_summary: list[str] = Field(
        default_factory=list,
        description="List of historical summaries for the entity",
    )
    categories: str
    relationships: list[dict[str, str]] = Field(
        default_factory=list,
        description="List of relationships with other entities",
    )
