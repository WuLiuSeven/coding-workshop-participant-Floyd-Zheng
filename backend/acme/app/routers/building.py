from app.dependencies import get_db, require_role, get_current_user
from app.models import Building, User, Role
from app.schemas.building import BuildingBase, BuildingRead
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func


router = APIRouter(prefix="/building", tags=["building"])

@router.get("", response_model=list[BuildingRead])
async def list_building(db: AsyncSession = Depends(get_db), 
    _: User = Depends(get_current_user)) -> list[BuildingRead]:

    statement = select(Building).order_by(Building.id)
    result = await db.execute(statement)
    return list(result.scalars().all())

@router.post("", response_model=BuildingRead, status_code=status.HTTP_201_CREATED)
async def create_building(payload: BuildingBase, db: AsyncSession = Depends(get_db)
                           , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                           ) -> BuildingRead:

    building = Building(**payload.model_dump())
    db.add(building)
    await db.commit()
    await db.refresh(building)
    return building

@router.delete("/{building_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_building(
    building_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN))
    ) -> None:
    building = await db.get(Building, building_id)

    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Building '{building_id}' not found"
        )
    await db.delete(building)
    await db.commit()

@router.patch("/{building_id}", response_model=BuildingBase)
async def update_building(building_id: int, payload: BuildingBase, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                        ) -> Building:
    building = await db.get(Building, building_id)

    if building is None:
        raise HTTPException(
                    status_code=status.HTTP_404_NOT_Found,
                    detail=f"Building '{building_id}' not found"
                )

    building.name = payload.name
    building.facility_id = payload.facility_id

    await db.commit()
    await db.refresh(building)

    return building


@router.get("/{building_id}", response_model=BuildingRead)
async def get_building(building_id: int, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(get_current_user)
                        ) -> BuildingRead:
    building = await db.get(Building, building_id)

    if building is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Building {building_id} not found"
        )

    return building

