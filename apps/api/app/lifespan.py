from contextlib import asynccontextmanager
from fastapi import FastAPI
from apps.api.app.core.logging import configure_logging
from packages.database.sessions import init_database

@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    init_database()
    yield
