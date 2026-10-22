
from app.dependencies import get_db, require_role, get_current_user
from app.models import Ticket, User, Role
from app.schemas.ticket import TicketBase, TicketRead, TicketUpdate
from app.models import Engineer, Incident
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from fastapi import APIRouter, Depends, status, HTTPException


router = APIRouter(prefix="/ticket", tags=["ticket"])


@router.get("", response_model=list[TicketRead])
async def list_tickets(db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
) -> list[TicketRead]:

    statement = select(Ticket).order_by(Ticket.id)
    result = await db.execute(statement)

    return list(result.scalars().all())


@router.post("", response_model=TicketRead, status_code=status.HTTP_201_CREATED,)
async def create_ticket(payload: TicketBase, db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN)),
    ) -> TicketRead:

    engineer = await db.get(Engineer, payload.engineer_id)
    if engineer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Engineer {payload.engineer_id} not found",
        )

    incident = await db.get(Incident, payload.incident_id)
    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {payload.incident_id} not found",
        )

    # Mistake, incident already resolved
    if incident.resolved_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Incident {incident.id} is already completed",
        )

    ticket = Ticket(**payload.model_dump())
    db.add(ticket)
    engineer.at_incident = incident.id
    engineer.is_available = False
    await db.commit()
    await db.refresh(ticket)

    # first ticket on this incident: acknowledged_at = ticket.created_at
    if incident.acknowledged_at is None:
        incident.acknowledged_at = ticket.created_at
        await db.commit()
        await db.refresh(ticket)

    return ticket

# Engineers get the tickets assigned to them; everyone else gets tickets on incidents they reported.
@router.get("/mine", response_model=list[TicketRead])
async def list_my_tickets(db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    ) -> list[TicketRead]:
    if current_user.role == Role.ENGINEER:
        statement = (
            select(Ticket)
            .join(Engineer, Ticket.engineer_id == Engineer.id)
            .where(Engineer.user_id == current_user.id)
        )
    else:
        statement = (
            select(Ticket)
            .join(Incident, Ticket.incident_id == Incident.id)
            .where(Incident.reported_by == current_user.id)
        )
    result = await db.execute(statement.order_by(Ticket.created_at.desc()))
    return list(result.scalars().all())

@router.get("/{ticket_id}", response_model=TicketRead)
async def get_ticket(ticket_id: int, db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    ) -> TicketRead:

    ticket = await db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    return ticket


@router.patch("/{ticket_id}", response_model=TicketRead)
async def update_ticket(ticket_id: int, payload: TicketUpdate, db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN)),
    ) -> TicketRead:

    ticket = await db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null",
            )

        if field == "engineer_id":
            engineer = await db.get(Engineer, value)
            if engineer is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Engineer {value} not found",
                )

        elif field == "incident_id":
            incident = await db.get(Incident, value)
            if incident is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Incident {value} not found",
                )

        setattr(ticket, field, value)

    await db.commit()
    await db.refresh(ticket)

    return ticket


@router.delete("/{ticket_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ticket(ticket_id: int, db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN)),
    ) -> None:

    ticket = await db.get(Ticket, ticket_id)

    if ticket is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Ticket {ticket_id} not found",
        )

    engineer = await db.get(Engineer, ticket.engineer_id)

    # Free the engineer from the deleted ticket
    if engineer is not None and engineer.at_incident == ticket.incident_id:
        engineer.at_incident = None
        engineer.is_available = True

    await db.delete(ticket)
    await db.commit()
