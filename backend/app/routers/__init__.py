from fastapi import APIRouter

from app.routers import estimates, history_router, rooms, settings, tiles

api_router = APIRouter(prefix="/api")
api_router.include_router(rooms.router)
api_router.include_router(tiles.router)
api_router.include_router(estimates.router)
api_router.include_router(history_router.router)
api_router.include_router(settings.router)
