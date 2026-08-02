from fastapi import APIRouter

from app.api.v1 import documents, pets

router = APIRouter(prefix="/v1")
router.include_router(pets.router)
router.include_router(documents.router)
