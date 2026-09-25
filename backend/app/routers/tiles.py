from fastapi import APIRouter, HTTPException

from app.repositories import tiles as tile_repo

router = APIRouter(tags=["tiles"])


@router.get("/tiles")
def list_tiles():
    return {"items": tile_repo.list_tiles()}


@router.get("/tiles/{tile_id}")
def get_tile(tile_id: int):
    row = tile_repo.get_tile(tile_id)
    if not row:
        raise HTTPException(404, "tile not found")
    return row
