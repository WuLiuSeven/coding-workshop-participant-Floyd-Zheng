from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select, func, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError


from app.dependencies import get_db, get_current_user, require_role
from app.models import User, Role, Engineer, Team
from app.schemas.users import Token, UserCreate, UserRead, UserBase
from app.security import create_access_token, hash_password, verify_password
from datetime import datetime, timedelta, timezone
import uuid
import jwt
import os

SECRET_KEY = os.environ.get("SECRET_KEY", "<replace-with-a-real-secret-key>")


router = APIRouter(prefix="/auth", tags=["auth"])
@router.post("/token", response_model=Token)
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalar_one_or_none()

    print("LOGIN EMAIL:", form_data.username)
    print("USER FOUND:", user is not None)

    if user:
        print("USER ID:", user.id)
        print("USER ROLE:", user.role)

    # check to verify if the password is correct
    if user is None or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"}
        )
        

    access_token = create_access_token(data={"sub": user.email, "role": user.role.value})

    return Token(
        access_token=access_token,
        token_type="bearer",
    )

# function to register a new user, requires the highest role
@router.post("/register", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(
    payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    _ : User = Depends(require_role(Role.FACILITY_ADMIN)),
) -> User:
    #Password checker TODO
    existing = await db.execute(select(User).where(func.lower(User.email) == payload.email.lower()))
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{payload.email}' is already used",
        )

    user = User(
        email = payload.email,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user

# function to register a new employee
@router.post("/registerEmployee", response_model=UserRead, status_code=status.HTTP_201_CREATED)
async def register_user(payload: UserCreate,
    db: AsyncSession = Depends(get_db),
    ) -> User:

    # Ensure email contains "acme.inc"
    if "acme.inc" not in payload.email.lower():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email must contain 'acme.inc'",
        )

    # Check if email already exists (case-insensitive)
    existing = await db.execute(
        select(User).where(
            func.lower(User.email) == payload.email.lower()
        )
    )

    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Email '{payload.email}' is already used",
        )

    user = User(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        first_name=payload.first_name,
        last_name=payload.last_name,
        role=payload.role,
    )

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user

def invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
        headers={"WWW-Authenticate": "Bearer"},
    )

@router.get("", response_model=list[UserRead])
async def list_user(db: AsyncSession = Depends(get_db), 
    _: User = Depends(require_role(Role.FACILITY_ADMIN))) -> list[UserRead]:

    statement = select(User).order_by(User.id)
    result = await db.execute(statement)
    return list(result.scalars().all())


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN))
    ) -> None:
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User '{user_id}' not found"
        )
    await db.delete(user)
    await db.commit()

@router.patch("/{user_id}", response_model=UserBase)
async def update_user(
    user_id: int,
    payload: UserBase,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN)),
) -> User:
    user = await db.get(User, user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User {user_id} not found")

    if payload.role == Role.FACILITY_ADMIN and user.role != Role.FACILITY_ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admins can only be created in code")

    existing_user = await db.scalar(select(User).where(User.email == payload.email, User.id != user_id))
    if existing_user:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email is already in use")

    promoted = payload.role == Role.ENGINEER and user.role != Role.ENGINEER

    user.email = payload.email
    user.first_name = payload.first_name
    user.last_name = payload.last_name
    user.is_active = payload.is_active
    user.role = payload.role

    # promoting to Engineer also creates their engineer record (once)
    if promoted:
        has_record = await db.scalar(select(Engineer).where(Engineer.user_id == user.id))
        if has_record is None:
            db.add(Engineer(user_id=user.id, is_available=True, at_incident=None, team='Equipment'))

    await db.commit()
    await db.refresh(user)
    return user


@router.get("/{user_id}", response_model=UserRead)
async def get_user(user_id: int, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                        ) -> UserRead:
    user = await db.get(User, user_id)

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found"
        )

    return user