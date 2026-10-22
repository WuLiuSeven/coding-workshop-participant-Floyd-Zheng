from app.dependencies import get_db, require_role, get_current_user
from app.models import Engineer, User, Role, Team
from app.schemas.engineer import EngineerBase, EngineerRead
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import APIRouter, Depends, status, HTTPException
from sqlalchemy import select, func


router = APIRouter(prefix="/engineer", tags=["engineer"])

@router.get("", response_model=list[EngineerRead])
async def list_engineer(db: AsyncSession = Depends(get_db), 
    _: User = Depends(require_role(Role.FACILITY_ADMIN))) -> list[EngineerRead]:

    statement = select(Engineer).order_by(Engineer.id)
    result = await db.execute(statement)
    return list(result.scalars().all())

@router.post("", response_model=EngineerRead, status_code=status.HTTP_201_CREATED)
async def create_engineer(payload: EngineerBase, db: AsyncSession = Depends(get_db)
                           , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                           ) -> EngineerRead:

    engineer = Engineer(**payload.model_dump())
    db.add(engineer)
    await db.commit()
    await db.refresh(engineer)
    return engineer

@router.delete("/{engineer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_engineer(
    engineer_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN))
    ) -> None:
    engineer = await db.get(Engineer, engineer_id)

    if engineer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engineer '{engineer_id}' not found"
        )
    await db.delete(engineer)
    await db.commit()

@router.patch("/{engineer_id}", response_model=EngineerBase)
async def update_engineer(engineer_id: int, payload: EngineerBase, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                        ) -> Engineer:
    engineer = await db.get(Engineer, engineer_id)

    if engineer is None:
        raise HTTPException(
                    status_code=status.HTTP_404_NOT_Found,
                    detail=f"Engineer '{engineer}' not found"
                )

    engineer.is_available = payload.is_available
    #at_incident: int | None
    engineer.at_incident = payload.at_incident
    engineer.team = payload.team
    engineer.user_id = payload.user_id
    

    await db.commit()
    await db.refresh(engineer)

    return engineer


@router.get("/{engineer_id}", response_model=EngineerRead)
async def get_engineer(engineer_id: int, db: AsyncSession = Depends(get_db)
                        , _: User = Depends(require_role(Role.FACILITY_ADMIN))
                        ) -> EngineerRead:
    engineer = await db.get(Engineer, engineer_id)

    if engineer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engineer {engineer_id} not found"
        )

    return engineer

