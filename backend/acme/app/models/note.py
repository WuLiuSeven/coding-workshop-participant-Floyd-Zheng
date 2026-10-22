from __future__ import annotations
from datetime import datetime 
from typing import TYPE_CHECKING
from sqlalchemy import DateTime, ForeignKey, String, func 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

if TYPE_CHECKING: 
    from .incident import Incident

class Note(Base): 
    __tablename__ = "notes"

    id: Mapped[int] = mapped_column(primary_key=True)
    comments: Mapped[str | None] = mapped_column(String(250), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())
    incident_at: Mapped[int] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )

    incident: Mapped["Incident"] = relationship(back_populates="notes")

    def __repr__(self) -> str:
        return f"Note(id={self.id}, incident={self.incident})"