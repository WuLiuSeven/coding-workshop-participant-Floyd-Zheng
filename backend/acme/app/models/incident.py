from __future__ import annotations
from typing import TYPE_CHECKING 
from datetime import datetime
from sqlalchemy import Boolean, DateTime, Enum as SQLEnum, ForeignKey, String , func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base 
from .enums import Priority, Status, Category

if TYPE_CHECKING: 
    from .user import User 
    from .engineer import Engineer 
    from .ticket import Ticket 
    from .note import Note
    from .seat import Seat

class Incident(Base): 
    __tablename__ = "incidents"

    id: Mapped[int] = mapped_column(primary_key=True)

    status: Mapped[Status] = mapped_column(
        SQLEnum(Status, name="incident_status", 
        values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False
    )

    priority: Mapped[Priority] = mapped_column(
        SQLEnum(Priority, name="incident_priority", 
        values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False
    )

    category: Mapped[Category] = mapped_column(
        SQLEnum(Category, name="incident_category",
        values_callable=lambda enum_cls: [member.value for member in enum_cls]),
        nullable=False
    )

    is_escalated: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    acknowledged_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    reported_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    resolved_by: Mapped[int | None] = mapped_column(ForeignKey("engineers.id"), nullable=True)
    seat_id: Mapped[int] = mapped_column(ForeignKey("seats.id"), nullable=False)
    incident_notes: Mapped[str | None] = mapped_column(String(120), nullable=True)
    #

    user: Mapped["User"] = relationship(back_populates="incidents")
    engineer: Mapped["Engineer | None"] = relationship(back_populates="incidents")
    tickets: Mapped[list["Ticket"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    notes: Mapped[list["Note"]] = relationship(
        back_populates="incident",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    seat: Mapped["Seat"] = relationship(back_populates="incidents")

    def __repr__(self) -> str:
        return (
            f"Incident(id={self.id},"
            f"status={self.status.value!r},"
            f"priority={self.priority.value!r},"
            f"category={self.category.value!r})"
        )