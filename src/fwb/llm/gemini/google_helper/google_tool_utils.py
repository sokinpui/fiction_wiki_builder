# google_tool_utils.py
from typing import Dict, List, Optional, Type

from google.ai.generativelanguage import (
    FunctionDeclaration,
    Schema,
    Tool,
)
from google.ai.generativelanguage import Type as GoogleApiType
from pydantic import BaseModel

TYPE_MAP = {
    "string": GoogleApiType.STRING,
    "integer": GoogleApiType.INTEGER,
    "number": GoogleApiType.NUMBER,
    "boolean": GoogleApiType.BOOLEAN,
    "array": GoogleApiType.ARRAY,
    "object": GoogleApiType.OBJECT,
}


def pydantic_to_google_tool(pydantic_model: Type[BaseModel]) -> Tool:
    schema_dict = pydantic_model.model_json_schema()
    properties = schema_dict.get("properties", {})
    required_fields = schema_dict.get("required", [])
    model_description = schema_dict.get(
        "description", pydantic_model.__doc__ or f"Schema for {pydantic_model.__name__}"
    )
    google_properties: Dict[str, Schema] = {}
    for name, prop_schema in properties.items():
        google_type = GoogleApiType.TYPE_UNSPECIFIED
        prop_description = prop_schema.get("description", "")
        items_schema: Optional[Schema] = None
        prop_type_str: Optional[str] = None

        if "anyOf" in prop_schema:  # Handling for Optional fields (type | None)
            for type_option in prop_schema["anyOf"]:
                if type_option.get("type") != "null":
                    prop_type_str = type_option.get("type")
                    prop_description = type_option.get("description", prop_description)
                    if (
                        "items" in type_option
                    ):  # Source items schema correctly for arrays within anyOf
                        prop_schema["items"] = type_option["items"]
                    break
        else:
            prop_type_str = prop_schema.get("type")

        if prop_type_str:
            google_type = TYPE_MAP.get(prop_type_str, GoogleApiType.TYPE_UNSPECIFIED)

        if google_type == GoogleApiType.ARRAY and "items" in prop_schema:
            items_prop_schema = prop_schema["items"]
            # Handle cases where 'items' could be a reference or complex object
            if isinstance(items_prop_schema, dict) and "type" in items_prop_schema:
                items_type_str = items_prop_schema.get("type")
                items_google_type = TYPE_MAP.get(
                    items_type_str, GoogleApiType.TYPE_UNSPECIFIED
                )
                if items_google_type != GoogleApiType.TYPE_UNSPECIFIED:
                    items_schema = Schema(
                        type=items_google_type,
                        description=items_prop_schema.get("description", ""),
                    )

        if google_type != GoogleApiType.TYPE_UNSPECIFIED:
            google_properties[name] = Schema(
                type=google_type, description=prop_description, items=items_schema
            )
        # else: Silently skip properties with unmapped types

    function_declaration = FunctionDeclaration(
        name=pydantic_model.__name__,
        description=model_description,
        parameters=Schema(
            type=GoogleApiType.OBJECT,
            properties=google_properties,
            required=required_fields,
        ),
    )
    return Tool(function_declarations=[function_declaration])
