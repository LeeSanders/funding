from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import inspect, text

from app.api.routes import router
from app.core.config import settings
from app.db.database import Base, SessionLocal, engine
from app import models  # noqa: F401
from app.services.bootstrap import seed_database


def ensure_runtime_schema() -> None:
    inspector = inspect(engine)
    with engine.begin() as connection:
        if "valuation_snapshots" in inspector.get_table_names():
            valuation_columns = {column["name"] for column in inspector.get_columns("valuation_snapshots")}
            if "valuation_method" not in valuation_columns:
                connection.execute(
                    text(
                        "ALTER TABLE valuation_snapshots "
                        "ADD COLUMN valuation_method VARCHAR(32) NOT NULL DEFAULT 'cached'"
                    )
                )

        if "ocr_extraction_items" in inspector.get_table_names():
            ocr_columns = {column["name"] for column in inspector.get_columns("ocr_extraction_items")}
            if "profit" not in ocr_columns:
                connection.execute(
                    text(
                        "ALTER TABLE ocr_extraction_items "
                        "ADD COLUMN profit FLOAT NOT NULL DEFAULT 0"
                    )
                )


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    ensure_runtime_schema()
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()
    yield


app = FastAPI(title=settings.app_name, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:8787",
        "http://localhost:8787",
        "http://127.0.0.1:5173",
        "http://localhost:5173",
        "http://127.0.0.1:5174",
        "http://localhost:5174",
        "http://127.0.0.1:5175",
        "http://localhost:5175",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router, prefix=settings.api_prefix)
