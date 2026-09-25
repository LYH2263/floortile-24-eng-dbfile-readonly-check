from fastapi import APIRouter

from app.repositories import settings_repo

router = APIRouter(tags=["settings"])


@router.get("/settings")
def get_settings():
    return settings_repo.get_all()
