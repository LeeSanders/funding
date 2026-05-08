from app import models  # noqa: F401
from app.db.database import Base, SessionLocal, engine
from app.services.bootstrap import seed_database


def main() -> None:
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        seed_database(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
