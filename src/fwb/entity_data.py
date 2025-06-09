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

    category: str
    relationships: dict[str, str] = Field(
        default_factory=dict,
        description="List of relationships with other entities",
    )
