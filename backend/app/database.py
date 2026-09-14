import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import DeclarativeBase, Session


class Base(DeclarativeBase):
    pass


def database_url() -> URL:
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    password = os.getenv("DB_PASSWORD")
    if not password or password == "replace_with_your_local_password":
        raise RuntimeError("Set DB_PASSWORD in backend/.env before using the database.")
    return URL.create(
        "postgresql+psycopg",
        username=os.getenv("DB_USER", "signalradar"),
        password=password,
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "9912")),
        database=os.getenv("DB_NAME", "signalradar"),
    )


@lru_cache
def get_engine():
    return create_engine(database_url(), pool_pre_ping=True, connect_args={"connect_timeout": 5})


def get_session():
    with Session(get_engine()) as session:
        yield session
