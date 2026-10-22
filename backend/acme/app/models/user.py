from __future__ import annotations
from typing import TYPE_CHECKING
from sqlalchemy import Boolean, Enum as SQLEnum, String 
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .base import Base 
from .enums import Role

if TYPE_CHECKING: 
    from .incident import Incident 
    from .engineer import Engineer

class User(Base): 
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    first_name: Mapped[str] = mapped_column(String(100), nullable=False)
    last_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)

    role: Mapped[Role] = mapped_column(
        SQLEnum(
            Role,
            name="user_role",
            values_callable=lambda enum_cls: [member.value for member in enum_cls]
        ),
    default=Role.EMPLOYEE,
    nullable=False,
    )

    incidents: Mapped[list["Incident"]] = relationship(back_populates="user")
    engineer: Mapped["Engineer | None"] = relationship(back_populates="user", uselist=False)

    def __repr__(self) -> str:
        return f"User(id={self.id}, email={self.email!r}, role={self.role.value!r})"