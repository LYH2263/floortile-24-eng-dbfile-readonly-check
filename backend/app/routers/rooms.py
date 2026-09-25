from fastapi import APIRouter, HTTPException

from app.repositories import rooms as room_repo

router = APIRouter(tags=["rooms"])


@router.get("/rooms")
def list_rooms():
    return {"items": room_repo.list_rooms()}


@router.get("/rooms/{room_id}")
def get_room(room_id: int):
    row = room_repo.get_room(room_id)
    if not row:
        raise HTTPException(404, "room not found")
    return row
