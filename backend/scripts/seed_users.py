import asyncio
from app.database import AsyncSessionLocal
from app.models import User, Role
from app.security import hash_password

async def seed_users() -> None:
    async with AsyncSessionLocal() as session:
        session.add_all([
            User(email="admin@acme.com", first_name="Alice", last_name="Alton", is_active=True, hashed_password=hash_password("Adminadmin"), role=Role.FACILITY_ADMIN),
            User(email="engineer@acme.com", first_name="Bob", last_name="Boyle", is_active=True, hashed_password=hash_password("Engineer"), role=Role.ENGINEER),
            User(email="employee@acme.com", first_name="Chase", last_name="Canton", is_active=True, hashed_password=hash_password("Employee"), role=Role.EMPLOYEE)
        ])
        await session.commit()
if __name__ == "__main__":
    asyncio.run(seed_users())