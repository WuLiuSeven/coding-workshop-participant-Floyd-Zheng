from app.dependencies import get_db, require_role, get_current_user
from app.models import Floor, User, Role, Building
from app.schemas.floor import FloorBase, FloorRead
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func


router = APIRouter(prefix="/floor", tags=["floor"])

@router.get("", response_model=list[FloorRead])
async def list_floor(db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user)) -> list[FloorRead]:

    statement = select(Floor).order_by(Floor.id)
    result = await db.execute(statement)
    return list(result.scalars().all())

@router.post("", response_model=FloorRead, status_code=status.HTTP_201_CREATED)
async def create_floor(payload: FloorBase, db: AsyncSession = Depends(get_db)
                           , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                           ) -> FloorRead:

    building = await db.get(Building, payload.building_id)
    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Building {payload.building_id} not found",
        )

    floor = Floor(**payload.model_dump())
    db.add(floor)
    await db.commit()
    await db.refresh(floor)
    return floor

@router.delete("/{floor_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_floor(
    floor_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN))
    ) -> None:
    floor = await db.get(Floor, floor_id)

    if floor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor '{floor_id}' not found"
        )
    await db.delete(floor)
    await db.commit()

@router.patch("/{floor_id}", response_model=FloorBase)
async def update_floor(floor_id: int, payload:FloorBase, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                        ) -> Floor:
    floor = await db.get(Floor, floor_id)

    building = await db.get(Building, payload.building_id)
    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Building {payload.building_id} not found",
        )

    if floor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor {floor_id} not found",
        )
    floor.floor_number = payload.floor_number
    floor.building_id = payload.building_id

    await db.commit()
    await db.refresh(floor)

    return floor


@router.get("/{floor_id}", response_model=FloorRead)
async def get_floor(floor_id: int, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(get_current_user)
                        ) -> FloorRead:
    floor = await db.get(Floor, floor_id)

    if floor is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Floor {floor_id} not found"
        )

    return floor

