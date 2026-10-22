from app.dependencies import get_db, require_role, get_current_user
from app.models import Facility, User, Role
from app.schemas.facility import FacilityBase, FacilityRead
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func


router = APIRouter(prefix="/facility", tags=["facility"])

@router.get("", response_model=list[FacilityRead])
async def list_facility(db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user)) -> list[FacilityRead]:

    statement = select(Facility).order_by(Facility.id)
    result = await db.execute(statement)
    return list(result.scalars().all())

@router.post("", response_model=FacilityRead, status_code=status.HTTP_201_CREATED)
async def create_facility(payload: FacilityBase, db: AsyncSession = Depends(get_db)
                           , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                           ) -> FacilityRead:

    facility = Facility(**payload.model_dump())
    db.add(facility)
    await db.commit()
    await db.refresh(facility)
    return facility

@router.delete("/{facility_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_facility(
    facility_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN))
    ) -> None:
    facility = await db.get(Facility, facility_id)

    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility '{facility_id}' not found"
        )
    await db.delete(facility)
    await db.commit()

@router.patch("/{facility_id}", response_model=FacilityBase)
async def update_facility(facility_id: int, payload: FacilityBase, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                        ) -> Facility:
    facility = await db.get(Facility, facility_id)

    if facility is None:
        raise HTTPException(
                    status_code=status.HTTP_404_NOT_Found,
                    detail=f"Facility '{facility}' not found"
                )

    facility.name = payload.name

    await db.commit()
    await db.refresh(facility)

    return facility


@router.get("/{facility_id}", response_model=FacilityRead)
async def get_facility(facility_id: int, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(get_current_user)
                        ) -> FacilityRead:
    facility = await db.get(Facility, facility_id)

    if facility is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Facility {facility_id} not found"
        )

    return facility

