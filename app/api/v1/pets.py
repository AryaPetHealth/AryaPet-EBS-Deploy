from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentDbUser
from app.db.models.pet import Pet
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.pet import PetCreate, PetRead, PetUpdate
from app.services.patient_id import generate_patient_id

router = APIRouter(prefix="/pets", tags=["pets"])

_MAX_PATIENT_ID_ATTEMPTS = 5


async def _get_owned_pet(patient_id: str, current_user: User, db: AsyncSession) -> Pet:
    result = await db.execute(
        select(Pet).where(Pet.patient_id == patient_id, Pet.owner_id == current_user.id)
    )
    pet = result.scalar_one_or_none()
    if pet is None:
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
    # patient_id collisions are vanishingly unlikely (32^6 keyspace) but retried rather
    # than trusted blindly, since it's the pet's public identifier.
    for attempt in range(_MAX_PATIENT_ID_ATTEMPTS):
        pet = Pet(
            owner_id=current_user.id,
            name=payload.name,
            species=payload.species,
            patient_id=generate_patient_id(),
        )
        db.add(pet)
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            if attempt == _MAX_PATIENT_ID_ATTEMPTS - 1:
                raise
            continue
        await db.refresh(pet)
        return pet


@router.get("/{patient_id}", response_model=PetRead)
async def get_pet(
    patient_id: str,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> Pet:
    return await _get_owned_pet(patient_id, current_user, db)


@router.patch("/{patient_id}", response_model=PetRead)
async def update_pet(
    patient_id: str,
    payload: PetUpdate,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> Pet:
    pet = await _get_owned_pet(patient_id, current_user, db)
    updates = payload.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(pet, field, value)
    await db.commit()
    await db.refresh(pet)
    return pet


@router.delete("/{patient_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_pet(
    patient_id: str,
    current_user: CurrentDbUser,
    db: AsyncSession = Depends(get_db),
) -> None:
    pet = await _get_owned_pet(patient_id, current_user, db)
    await db.delete(pet)
    await db.commit()
