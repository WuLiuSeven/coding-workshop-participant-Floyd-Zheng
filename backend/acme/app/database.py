# import os
# from sqlalchemy import URL
# from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# DATABASE_URL = URL.create(
#     "postgresql+asyncpg",
#     username=os.environ.get("POSTGRES_USER") or "postgres",
#     password=os.environ.get("POSTGRES_PASS") or "postgres",
#     host=os.environ.get("POSTGRES_HOST", "localhost"),
#     port=int(os.environ.get("POSTGRES_PORT", "5432")),
#     database=os.environ.get("POSTGRES_NAME") or "test_data",
# )

# engine = create_async_engine(DATABASE_URL, echo=True)
# AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)
import os
from sqlalchemy import URL
from sqlalchemy.pool import NullPool
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

IS_LOCAL = os.environ.get("IS_LOCAL", "true").lower() == "true"

DATABASE_URL = URL.create(
    "postgresql+asyncpg",
    username=os.environ.get("POSTGRES_USER") or "postgres",
    password=os.environ.get("POSTGRES_PASS") or "postgres",
    host=os.environ.get("POSTGRES_HOST", "localhost"),
    port=int(os.environ.get("POSTGRES_PORT", "5432")),
    database=os.environ.get("POSTGRES_NAME") or "test_data",
)

engine = create_async_engine(
    DATABASE_URL,
    echo=IS_LOCAL,                                  # SQL logging only on your machine
    poolclass=None if IS_LOCAL else NullPool,       # Lambda: fresh connection per request
    connect_args={} if IS_LOCAL else {"ssl": "require"},   # Aurora requires SSL
)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)