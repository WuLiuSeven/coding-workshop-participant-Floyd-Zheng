
from app.dependencies import get_db, require_role, get_current_user
from app.models import Note, Incident, User, Role
from app.schemas.note import NoteBase, NoteUpdate, NoteRead
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from fastapi import APIRouter, Depends, status, HTTPException


router = APIRouter(prefix="/note", tags=["note"])


@router.get("", response_model=list[NoteRead])
async def list_notes(db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    ) -> list[NoteRead]:

    statement = select(Note).order_by(Note.id)
    result = await db.execute(statement)

    return list(result.scalars().all())


@router.post("", response_model=NoteRead, status_code=status.HTTP_201_CREATED)
async def create_note(payload: NoteBase, db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    ) -> NoteRead:

    incident = await db.get(Incident, payload.incident_at)

    if incident is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Incident {payload.incident_at} not found",
        )

    note = Note(**payload.model_dump())

    db.add(note)
    await db.commit()
    await db.refresh(note)

    return note


@router.get("/{note_id}", response_model=NoteRead)
async def get_note(note_id: int, db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_user),
    ) -> NoteRead:

    note = await db.get(Note, note_id)

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found",
        )

    return note


@router.patch("/{note_id}", response_model=NoteRead)
async def update_note(note_id: int, payload: NoteUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN)),
    ) -> NoteRead:

    note = await db.get(Note, note_id)

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found",
        )

    updates = payload.model_dump(exclude_unset=True)

    for field, value in updates.items():
        if value is None:
            raise HTTPException(
                status_code=422,
                detail=f"{field} cannot be null",
            )

        if field == "incident_at":
            incident = await db.get(Incident, value)
            if incident is None:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Incident {value} not found",
                )

        setattr(note, field, value)
            

    await db.commit()
    await db.refresh(note)

    return note


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_note(note_id: int, db: AsyncSession = Depends(get_db),
    _: User = Depends(require_role(Role.FACILITY_ADMIN)),
    ) -> None:

    note = await db.get(Note, note_id)

    if note is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Note {note_id} not found",
        )

    await db.delete(note)
    await db.commit()
