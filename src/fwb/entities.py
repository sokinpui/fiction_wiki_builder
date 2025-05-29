# File: src/fwb/model/entities.py

from typing import List

# --- Base Classes ---


class Description:
    def __init__(self, chapter: int, text: str):
        self.chapter: int = chapter
        self.text: str = text


class Entity:
    def __init__(self, name: str):
        self.name: str = name
        self.descriptions: List[Description] = []
        self.relationships: List[Relationship] = []

    def add_description(self, description: Description):
        if not isinstance(description, Description):
            raise TypeError("description must be an instance of Description")
        self.descriptions.append(description)

    def add_relationship(self, relationship):
        if not isinstance(relationship, Relationship):
            raise TypeError("relationship must be an instance of Relationship")
        self.relationships.append(relationship)


class Relationship:
    def __init__(self, target: Entity):
        self.target: Entity = target
        self.descriptions: List[Description] = []

    def add_description(self, description: Description):
        if not isinstance(description, Description):
            raise TypeError("description must be an instance of Description")
        self.descriptions.append(description)


# --- Specific Entities ---


class MagicWeapon(Entity):
    def __init__(self, name: str):
        super().__init__(name)


class Character(Entity):
    def __init__(self, name: str):
        super().__init__(name)
        self.aliases: List[str] = []
        self.magic_weapons: List[MagicWeapon] = []

    def add_alias(self, alias: str):
        if alias not in self.aliases:
            self.aliases.append(alias)

    def add_magic_weapon(self, weapon: MagicWeapon):
        if not isinstance(weapon, MagicWeapon):
            raise TypeError("weapon must be an instance of MagicWeapon")
        if weapon not in self.magic_weapons:
            self.magic_weapons.append(weapon)


class Organization(Entity):
    def __init__(self, name: str):
        super().__init__(name)
        self.members: List[Character] = []

    def add_member(self, character: Character):
        if not isinstance(character, Character):
            raise TypeError("member must be an instance of Character")
        if character not in self.members:
            self.members.append(character)


class Area(Entity):

    def __init__(self, name: str):
        super().__init__(name)
        self.organizations_present: List[Organization] = []

    def add_organization(self, organization: Organization):
        if not isinstance(organization, Organization):
            raise TypeError("organization must be an instance of Organization")
        if organization not in self.organizations_present:
            self.organizations_present.append(organization)


class World(Entity):

    def __init__(self, name: str):
        super().__init__(name)
        self.areas: List[Area] = []

    def add_area(self, area: Area):
        if not isinstance(area, Area):
            raise TypeError("area must be an instance of Area")
        if area not in self.areas:
            self.areas.append(area)
