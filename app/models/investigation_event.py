import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional
from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.case import Case


class InvestigationEventType(str, enum.Enum):
    FIR_REGISTERED = "FIR_REGISTERED"
    STATEMENT_RECORDED = "STATEMENT_RECORDED"
    EVIDENCE_COLLECTED = "EVIDENCE_COLLECTED"
    SUSPECT_IDENTIFIED = "SUSPECT_IDENTIFIED"
    ARREST = "ARREST"
    SEARCH = "SEARCH"
    INTERROGATION = "INTERROGATION"
    CHARGESHEET_FILED = "CHARGESHEET_FILED"
    OTHER = "OTHER"


class InvestigationEvent(Base, TimestampMixin):
    __tablename__ = "investigation_events"

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
    event_type: Mapped[InvestigationEventType] = mapped_column(
        Enum(InvestigationEventType, name="investigation_event_type_enum", create_type=False),
        default=InvestigationEventType.OTHER,
        nullable=False,
        index=True
    )
    description: Mapped[Text] = mapped_column(Text, nullable=False)
    event_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    officer_reference: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="investigation_events")
