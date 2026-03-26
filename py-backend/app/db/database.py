from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
import os
from pathlib import Path

from dotenv import load_dotenv

# Ensure we always load the backend's .env (located at py-backend/.env),
# even when the process working directory is different (e.g. repo root).
ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
load_dotenv(dotenv_path=str(ENV_PATH))

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://postgres:YOUR_PASSWORD@localhost:5432/local_meta"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

with engine.connect() as conn:
    print("Connected successfully!")

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()