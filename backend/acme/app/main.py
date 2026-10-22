# from fastapi import FastAPI
# from sqlalchemy import text
# from .database import engine
# from app.routers import users, facility, building, floor, seat, engineer, incident, ticket, note
# from fastapi.middleware.cors import CORSMiddleware

# app = FastAPI(
#     title="ACME",
#     description="ACME WorkShop Project",
#     version="0.0.1"
# )

# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=[
#     "http://localhost:5173",
#     ],
#     # Frontend Origins aws
#     # allow_origins=[
#     # "http://agricore-frontend-fz4321.s3-website.us-east-2.amazonaws.com"
#     # ],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"]
# )

# app.include_router(users.router)
# app.include_router(engineer.router)
# app.include_router(ticket.router)
# app.include_router(incident.router)
# app.include_router(note.router)
# app.include_router(facility.router)
# app.include_router(building.router)
# app.include_router(floor.router)
# app.include_router(seat.router)

# @app.get("/health/db", tags=["health"])
# async def health_db() -> dict[str, str]:
#     async with engine.connect() as conn:
#         await conn.execute(text("SELECT 1"))
#     return {"database": "ok"}

# @app.get("/health", tags=["health"])
# async def health_check() -> dict[str, str]:
#     return {"status": "ok"}

from contextlib import asynccontextmanager
from app.seed import seed_users


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from .database import engine
import app.models as _all_models            # imports every model so Base knows about all tables
from app.models.base import Base
from app.routers import users, facility, building, floor, seat, engineer, incident, ticket, note

@asynccontextmanager
async def lifespan(_app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await seed_users()
    yield


app = FastAPI(
    title="ACME",
    description="ACME WorkShop Project",
    version="0.0.1",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(users.router)
app.include_router(engineer.router)
app.include_router(ticket.router)
app.include_router(incident.router)
app.include_router(note.router)
app.include_router(facility.router)
app.include_router(building.router)
app.include_router(floor.router)
app.include_router(seat.router)


@app.get("/health/db", tags=["health"])
async def health_db() -> dict[str, str]:
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"database": "ok"}


@app.get("/health", tags=["health"])
async def health_check() -> dict[str, str]:
    return {"status": "ok"}