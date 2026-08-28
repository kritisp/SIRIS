import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case
    from app.models.person import Person


class Phone(Base, TimestampMixin):
    __tablename__ = "phones"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    normalized_number: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    number_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)

    # Relationships
    person_associations: Mapped[List["PersonPhone"]] = relationship(
        "PersonPhone", back_populates="phone", cascade="all, delete-orphan"
    )
    case_associations: Mapped[List["CasePhone"]] = relationship(
        "CasePhone", back_populates="phone", cascade="all, delete-orphan"
    )


class PersonPhone(Base, TimestampMixin):
    __tablename__ = "person_phones"
    __table_args__ = (
        UniqueConstraint("person_id", "phone_id", name="uq_person_phone"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    person_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    phone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phones.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    person: Mapped["Person"] = relationship("Person", back_populates="phone_associations")
    phone: Mapped["Phone"] = relationship("Phone", back_populates="person_associations")


class CasePhone(Base, TimestampMixin):
    __tablename__ = "case_phones"
    __table_args__ = (
        UniqueConstraint("case_id", "phone_id", name="uq_case_phone"),
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
    phone_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("phones.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="phone_associations")
    phone: Mapped["Phone"] = relationship("Phone", back_populates="case_associations")
