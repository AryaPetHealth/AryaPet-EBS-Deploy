import uuid

from pydantic import BaseModel, ConfigDict


class PetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    species: str
