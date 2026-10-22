from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, ForeignKey, Enum as SQLEnum

from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base
from .enums import Team

if TYPE_CHECKING: 
    from .user import User 
    from .incident import Incident 
    from .ticket import Ticket

class Engineer(Base): 
    __tablename__ = "engineers"

    id: Mapped[int] = mapped_column(primary_key=True)
    is_available: Mapped[bool] = mapped_column(Boolean, default=True)
    at_incident: Mapped[int | None] = mapped_column(nullable=True)
    team: Mapped[Team] = mapped_column(
        SQLEnum(
            Team,
            name="engineer_team",
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
    nullable=False,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False)

    user: Mapped["User"] = relationship(back_populates="engineer")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="engineer")
    tickets: Mapped[list["Ticket"]] = relationship(back_populates="engineer")

    def __repr__(self) -> str:
        return f"Engineer(id={self.id}, user_id={self.user_id})"