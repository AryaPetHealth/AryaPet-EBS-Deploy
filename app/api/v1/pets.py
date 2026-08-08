import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentDbUser
from app.db.models.pet import Pet
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.pet import PetCreate, PetRead, PetUpdate

router = APIRouter(prefix="/pets", tags=["pets"])


async def _get_owned_pet(pet_id: uuid.UUID, current_user: User, db: AsyncSession) -> Pet:
    pet = await db.get(Pet, pet_id)
    if pet is None or pet.owner_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pet not found")
    return pet


@router.get("", response_model=list[PetRead])
async def list_pets(
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> list[Pet]:
    result = await db.execute(select(Pet).where(Pet.owner_id == current_user.id))
    return list(result.scalars().all())


@router.post("", response_model=PetRead, status_code=status.HTTP_201_CREATED)
async def create_pet(
    payload: PetCreate,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> Pet:
    pet = Pet(owner_id=current_user.id, name=payload.name, species=payload.species)
    db.add(pet)
    await db.commit()
    await db.refresh(pet)
    return pet


@router.get("/{pet_id}", response_model=PetRead)
async def get_pet(
    pet_id: uuid.UUID,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> Pet:
    return await _get_owned_pet(pet_id, current_user, db)


@router.patch("/{pet_id}", response_model=PetRead)
async def update_pet(
    pet_id: uuid.UUID,
    payload: PetUpdate,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> Pet:
    pet = await _get_owned_pet(pet_id, current_user, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(pet, field, value)
    await db.commit()
    await db.refresh(pet)
    return pet


@router.delete("/{pet_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    pet_id: uuid.UUID,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    pet = await _get_owned_pet(pet_id, current_user, db)
    await db.delete(pet)
    await db.commit()
