from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import seed
from app.routers import api_router

app = FastAPI(title="Floortile", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def _startup():
    seed.init_db()


app.include_router(api_router)


@app.get("/api/health")
def health():
    return {"ok": True, "project": "floortile"}
