import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.case import Case


class EvidenceType(str, enum.Enum):
    CCTV = "CCTV"
    MOBILE = "MOBILE"
    DOCUMENT = "DOCUMENT"
    VEHICLE = "VEHICLE"
    WEAPON = "WEAPON"
    DIGITAL = "DIGITAL"
    PHYSICAL = "PHYSICAL"
    OTHER = "OTHER"


class Evidence(Base, TimestampMixin):
    __tablename__ = "evidences"

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
    evidence_type: Mapped[EvidenceType] = mapped_column(
        Enum(EvidenceType, name="evidence_type_enum", create_type=False),
        default=EvidenceType.OTHER,
        nullable=False,
        index=True
    )
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="COLLECTED", nullable=False)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="evidences")
