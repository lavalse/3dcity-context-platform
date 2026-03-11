from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import query, health, buildings, buildings_write, features, chat, export, versions, areas, shelters
from app.database import get_pool, close_pool


@asynccontextmanager
async def lifespan(app: FastAPI):
    await get_pool()   # warm up DB pool on startup
    yield
    await close_pool()


app = FastAPI(
    title="3D City Context Platform",
    description="Natural language queries over Tokyo Taito-ku 3D city model data",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE"],
    allow_headers=["*"],
)

app.include_router(health.router, prefix="/api")
app.include_router(query.router, prefix="/api")
app.include_router(buildings.router, prefix="/api")
app.include_router(buildings_write.router, prefix="/api")
app.include_router(features.router, prefix="/api")
app.include_router(chat.router, prefix="/api")
app.include_router(export.router, prefix="/api")
app.include_router(versions.router, prefix="/api")
app.include_router(areas.router, prefix="/api")
app.include_router(shelters.router, prefix="/api")
