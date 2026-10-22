from app.dependencies import get_db, require_role, get_current_user
from app.models import Seat, User, Role
from app.schemas.seat import SeatBase, SeatRead
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func


router = APIRouter(prefix="/seat", tags=["seat"])

@router.get("", response_model=list[SeatRead])
async def list_seat(db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user)) -> list[SeatRead]:

    statement = select(Seat).order_by(Seat.id)
    result = await db.execute(statement)
    return list(result.scalars().all())

@router.post("", response_model=SeatRead, status_code=status.HTTP_201_CREATED)
async def create_seat(payload: SeatBase, db: AsyncSession = Depends(get_db)
                           , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                           ) -> SeatRead:

    seat = Seat(**payload.model_dump())
    db.add(seat)
    await db.commit()
    await db.refresh(seat)
    return seat

@router.delete("/{seat_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_seat(
    seat_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN))
    ) -> None:
    seat = await db.get(Seat, seat_id)

    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat '{seat_id}' not found"
        )
    await db.delete(seat)
    await db.commit()

@router.patch("/{seat_id}", response_model=SeatBase)
async def update_seat(seat_id: int, payload:SeatBase, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                        ) -> Seat:
    seat = await db.get(Seat, seat_id)

    if seat is None:
        raise HTTPException(
                    status_code=status.HTTP_404_NOT_Found,
                    detail=f"Seat '{seat}' not found"
                )

    seat.seat_number = payload.seat_number
    seat.floor_id = payload.floor_id

    await db.commit()
    await db.refresh(seat)

    return seat


@router.get("/{seat_id}", response_model=SeatRead)
async def get_seat(seat_id: int, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(get_current_user)
                        ) -> SeatRead:
    seat = await db.get(Seat, seat_id)

    if seat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Seat {seat_id} not found"
        )

    return seat

