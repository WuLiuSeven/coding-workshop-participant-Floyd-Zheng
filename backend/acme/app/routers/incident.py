
from datetime import datetime
from app.dependencies import get_db, require_role, get_current_user
from app.models import Incident, User, Role, Status, Priority, Category, Engineer
from app.schemas.incident import IncidentBase, IncidentUpdate, IncidentRead
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import APIRouter, Depends, status, HTTPException


router = APIRouter(prefix="/incident", tags=["incident"])

# Incidents created by get_current_user
@router.get("/mine", response_model=list[IncidentRead])
async def list_my_incidents(db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ) -> list[IncidentRead]:

    statement = (
        select(Incident)
        .where(Incident.reported_by == current_user.id)
        .order_by(Incident.created_at.desc())
    )

    result = await db.execute(statement)
    return list(result.scalars().all())

@router.get("", response_model=list[IncidentRead])
async def list_incidents(
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[IncidentRead]:

    statement = select(Incident).order_by(Incident.id)
    result = await db.execute(statement)

    return list(result.scalars().all())


@router.post("", response_model=IncidentRead, status_code=status.HTTP_201_CREATED,)
async def create_incident(payload: IncidentBase, db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    ) -> IncidentRead:

    incident = Incident(**payload.model_dump(exclude={"reported_by"}), reported_by=_.id)

    db.add(incident)
    await db.commit()
    await db.refresh(incident)

    return incident

@router.get("/{incident_id}", response_model=IncidentRead)
async def get_incident(incident_id: int, db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    ) -> IncidentRead:

    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    return incident


@router.patch("/{incident_id}/escalate", response_model=IncidentRead)
async def escalate_incident(
    incident_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> IncidentRead:

    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    incident.is_escalated = True

    await db.commit()
    await db.refresh(incident)

    return incident


# If a engineer resolves the ticket, free then and any other engineers working on it
@router.patch("/{incident_id}", response_model=IncidentRead)
async def update_incident(
    incident_id: int,
    payload: IncidentUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_role(Role.FACILITY_ADMIN, Role.ENGINEER)),
) -> IncidentRead:

    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    updates = payload.model_dump(exclude_unset=True)

    nullable_fields = {
        "acknowledged_at",
        "resolved_at",
        "resolved_by",
        "incident_notes",
    }

    for field, value in updates.items():
        if value is None and field not in nullable_fields:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"{field} cannot be null",
            )

        setattr(incident, field, value)
    
    # if the incident is resolve, set the engineer who resolved it, delete everyone else who was working on it
    if updates.get("resolved_at") is not None:
        result = await db.execute(select(Engineer).where(Engineer.at_incident == incident.id))
        for eng in result.scalars().all():
            if "resolved_by" not in updates and eng.user_id == current_user.id:
                incident.resolved_by = eng.id
            eng.at_incident = None
            eng.is_available = True

    await db.commit()
    await db.refresh(incident)

    return incident


@router.delete("/{incident_id}", status_code=status.HTTP_204_NO_CONTENT,)
async def delete_incident(incident_id: int, db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN)),
    ) -> None:

    incident = await db.get(Incident, incident_id)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {incident_id} not found",
        )

    await db.delete(incident)
    await db.commit()
