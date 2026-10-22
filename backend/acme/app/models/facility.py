from __future__ import annotations
from typing import TYPE_CHECKING
from .base import Base
from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .building import Building

class Facility(Base):
    __tablename__ = "facilities"

    id: Mapped[int] = mapped_column(primary_key = True)
    name: Mapped[str] = mapped_column(String(100))

    buildings: Mapped[list["Building"]] = relationship(back_populates="facility", 
    cascade="all, delete-orphan",
    passive_deletes=True)

    def __repr__(self):
        return (f"Facility(id={self.id}, name={self.name})")
