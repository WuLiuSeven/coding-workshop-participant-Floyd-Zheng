from __future__ import annotations
from datetime import datetime 
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, func 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

if TYPE_CHECKING: 
    from .engineer import Engineer 
    from .incident import Incident

class Ticket(Base): 
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    engineer_id: Mapped[int] = mapped_column(ForeignKey("engineers.id"), nullable=False)
    incident_id: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    engineer: Mapped["Engineer"] = relationship(back_populates="tickets")
    incident: Mapped["Incident"] = relationship(back_populates="tickets")

def __repr__(self) -> str:
    return f"Ticket(id={self.id}, engineer={self.engineer}, incident={self.incident})"