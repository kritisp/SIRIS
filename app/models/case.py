import uuid
from datetime import date, time
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Date, ForeignKey, Index, String, Text, Time
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.chargesheet import Chargesheet
    from app.models.evidence import Evidence
    from app.models.investigation_event import InvestigationEvent
    from app.models.legal_section import CaseLegalSection
    from app.models.location import Location
    from app.models.person import CasePerson
    from app.models.phone import CasePhone
    from app.models.vehicle import CaseVehicle


class Case(Base, TimestampMixin):
    __tablename__ = "cases"
    __table_args__ = (
        Index("ix_cases_fir_number", "fir_number"),
        Index("ix_cases_crime_type", "crime_type"),
        Index("ix_cases_crime_category", "crime_category"),
        Index("ix_cases_registration_date", "registration_date"),
        Index("ix_cases_incident_date", "incident_date"),
        Index("ix_cases_district", "district"),
        Index("ix_cases_police_station", "police_station"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    fir_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False
    )
    station_id: Mapped[str] = mapped_column(
        String(100), nullable=False, default="PS_BBSR_001", index=True
    )
    police_station: Mapped[str] = mapped_column(String(150), nullable=False)
    district: Mapped[str] = mapped_column(String(150), nullable=False)
    state: Mapped[str] = mapped_column(String(100), nullable=False)
    registration_date: Mapped[date] = mapped_column(Date, nullable=False)
    incident_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    incident_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True)
    crime_type: Mapped[str] = mapped_column(String(150), nullable=False)
    crime_category: Mapped[str] = mapped_column(String(150), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="UNDER_INVESTIGATION", nullable=False)

    location_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("locations.id", ondelete="SET NULL"),
        nullable=True,
        index=True
    )

    # Relationships
    location: Mapped[Optional["Location"]] = relationship("Location", back_populates="cases")
    person_associations: Mapped[List["CasePerson"]] = relationship(
        "CasePerson", back_populates="case", cascade="all, delete-orphan"
    )
    vehicle_associations: Mapped[List["CaseVehicle"]] = relationship(
        "CaseVehicle", back_populates="case", cascade="all, delete-orphan"
    )
    phone_associations: Mapped[List["CasePhone"]] = relationship(
        "CasePhone", back_populates="case", cascade="all, delete-orphan"
    )
    evidences: Mapped[List["Evidence"]] = relationship(
        "Evidence", back_populates="case", cascade="all, delete-orphan"
    )
    chargesheet: Mapped[Optional["Chargesheet"]] = relationship(
        "Chargesheet", back_populates="case", uselist=False, cascade="all, delete-orphan"
    )
    investigation_events: Mapped[List["InvestigationEvent"]] = relationship(
        "InvestigationEvent", back_populates="case", cascade="all, delete-orphan"
    )
    legal_section_associations: Mapped[List["CaseLegalSection"]] = relationship(
        "CaseLegalSection", back_populates="case", cascade="all, delete-orphan"
    )
