import enum
import uuid
from datetime import date
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Date, Enum, ForeignKey, String, Text, UniqueConstraint, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.phone import PersonPhone


class PersonRole(str, enum.Enum):
    ACCUSED = "ACCUSED"
    SUSPECT = "SUSPECT"
    VICTIM = "VICTIM"
    WITNESS = "WITNESS"
    COMPLAINANT = "COMPLAINANT"
    OTHER = "OTHER"


class Person(Base, TimestampMixin):
    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    date_of_birth: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    gender: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    identifier_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # Relationships
    case_associations: Mapped[List["CasePerson"]] = relationship(
        "CasePerson", back_populates="person", cascade="all, delete-orphan"
    )
    phone_associations: Mapped[List["PersonPhone"]] = relationship(
        "PersonPhone", back_populates="person", cascade="all, delete-orphan"
    )


class CasePerson(Base, TimestampMixin):
    __tablename__ = "case_persons"
    __table_args__ = (
        UniqueConstraint("case_id", "person_id", "role", name="uq_case_person_role"),
        Index("ix_case_person_role", "role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[PersonRole] = mapped_column(
        Enum(PersonRole, name="person_role_enum", create_type=False),
        default=PersonRole.OTHER,
        nullable=False
    )
    details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="person_associations")
    person: Mapped["Person"] = relationship("Person", back_populates="case_associations")
