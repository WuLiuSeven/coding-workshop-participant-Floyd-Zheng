from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.database import AsyncSessionLocal
from app.models import User, Role, Engineer, Team
from app.security import hash_password

SEED_USERS = [
    {"email": "admin@acme.com", "first_name": "Alice", "last_name": "Alton",
     "password": "Adminadmin", "role": Role.FACILITY_ADMIN},
    {"email": "engineer@acme.com", "first_name": "Bob", "last_name": "Boyle",
     "password": "Engineer", "role": Role.ENGINEER},
    {"email": "employee@acme.com", "first_name": "Chase", "last_name": "Canton",
     "password": "Employee", "role": Role.EMPLOYEE},
]


async def seed_users() -> None:
    """Create the seed accounts if they're missing. Safe to run on every startup."""
    async with AsyncSessionLocal() as session:
        try:
            for spec in SEED_USERS:
                user = await session.scalar(select(User).where(User.email == spec["email"]))
                if user is None:
                    user = User(
                        email=spec["email"],
                        first_name=spec["first_name"],
                        last_name=spec["last_name"],
                        is_active=True,
                        hashed_password=hash_password(spec["password"]),
                        role=spec["role"],
                    )
                    session.add(user)
                    await session.flush()          # assigns user.id

                # engineers need their engineer record to be assignable
                if user.role == Role.ENGINEER:
                    has_record = await session.scalar(select(Engineer).where(Engineer.user_id == user.id))
                    if has_record is None:
                        session.add(Engineer(user_id=user.id, is_available=True,
                                             at_incident=None, team=next(iter(Team))))
            await session.commit()
        except IntegrityError:
            # two cold starts seeded at the same moment; the other one won
            await session.rollback()