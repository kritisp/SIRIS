import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.case import Case


class LegalSection(Base, TimestampMixin):
    __tablename__ = "legal_sections"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    code: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    law_name: Mapped[str] = mapped_column(String(100), default="IPC", nullable=False, index=True)

    # Relationships
    case_associations: Mapped[List["CaseLegalSection"]] = relationship(
        "CaseLegalSection", back_populates="legal_section", cascade="all, delete-orphan"
    )


class CaseLegalSection(Base, TimestampMixin):
    __tablename__ = "case_legal_sections"
    __table_args__ = (
        UniqueConstraint("case_id", "legal_section_id", name="uq_case_legal_section"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    case_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("cases.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    legal_section_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("legal_sections.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="legal_section_associations")
    legal_section: Mapped["LegalSection"] = relationship(
        "LegalSection", back_populates="case_associations"
    )
