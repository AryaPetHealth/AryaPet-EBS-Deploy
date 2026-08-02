from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import CurrentUser
from app.db.session import get_db
from app.schemas.pet import PetRead

router = APIRouter(prefix="/pets", tags=["pets"])


@router.get("", response_model=list[PetRead])
async def list_pets(
    current_user: CurrentUser,
    db: AsyncSession = Depends(get_db),
) -> list[PetRead]:
    # Placeholder: no Pet model/business logic yet. Demonstrates auth + DB session wiring.
    return []
