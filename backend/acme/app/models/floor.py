from __future__ import annotations
from typing import TYPE_CHECKING
from .base import Base
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .building import Building
    from .seat import Seat

class Floor(Base):
    __tablename__ = "floors"

    id: Mapped[int] = mapped_column(primary_key = True)
    floor_number: Mapped[int] = mapped_column(Integer)
    building_id: Mapped[int] = mapped_column(Integer, ForeignKey("buildings.id", ondelete="CASCADE"))

    seats: Mapped[list["Seat"]] = relationship(
        back_populates="floor",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    building: Mapped["Building"] = relationship(back_populates="floors")

    def __repr__(self):
        return (f"Floor(id={self.id}, floor_number={self.floor_number})")
    
    