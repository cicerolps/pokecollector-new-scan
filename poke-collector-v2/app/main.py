from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import collection, health, scan
from app.db.session import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Poke Collector v2",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router, prefix="/api/v1", tags=["health"])
app.include_router(scan.router, prefix="/api/v1", tags=["scan"])
app.include_router(collection.router, prefix="/api/v1", tags=["collection"])
