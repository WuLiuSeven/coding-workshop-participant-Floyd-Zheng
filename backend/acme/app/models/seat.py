from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Integer, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base

if TYPE_CHECKING:
    from .floor import Floor
    from .incident import Incident

class Seat(Base):
    __tablename__ = "seats"

    id: Mapped[int] = mapped_column(primary_key = True)
    seat_number: Mapped[int | None] = mapped_column(Integer)
    floor_id: Mapped[int] = mapped_column(Integer, ForeignKey("floors.id", ondelete="CASCADE"))
    
    floor: Mapped["Floor"] = relationship(back_populates="seats")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="seat")

    def __repr__(self):
        return (f"Seat(id={self.id}, seat number={self.seat_number})")
