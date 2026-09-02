from pydantic import BaseModel, ConfigDict


class PetRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    name: str
    species: str


class PetCreate(BaseModel):
    name: str
    species: str


class PetUpdate(BaseModel):
    # Both optional — PATCH semantics, only provided fields are changed.
    name: str | None = None
    species: str | None = None
