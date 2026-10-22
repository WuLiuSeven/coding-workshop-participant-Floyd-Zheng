import asyncio
from app.database import engine
from app.models import Base

async def create_tables() -> None:
    async with engine.begin() as conn:
        print(Base.metadata.tables.keys())
        await conn.run_sync(Base.metadata.create_all)

if __name__ == "__main__":
    asyncio.run(create_tables())