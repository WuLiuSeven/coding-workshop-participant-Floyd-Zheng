from __future__ import annotations
from typing import TYPE_CHECKING
from .base import Base
from sqlalchemy import Integer, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .floor import Floor
    from .facility import Facility

class Building(Base):
    __tablename__ = "buildings"

    id: Mapped[int] = mapped_column(primary_key = True)
    name: Mapped[str] = mapped_column(String(50))
    facility_id: Mapped[int] = mapped_column(Integer, ForeignKey("facilities.id", ondelete="CASCADE"))

    floors: Mapped[list["Floor"]] = relationship(
        back_populates="building",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
    facility: Mapped["Facility"] = relationship(back_populates="buildings")

    def __repr__(self):
        return (f"Building(id={self.id}, name={self.name})")
