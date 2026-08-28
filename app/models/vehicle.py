import enum
import uuid
from typing import TYPE_CHECKING, List, Optional
from sqlalchemy import Enum, ForeignKey, String, UniqueConstraint, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base, TimestampMixin, GUID

if TYPE_CHECKING:
    from app.models.case import Case


class VehicleRole(str, enum.Enum):
    SUSPECT_VEHICLE = "SUSPECT_VEHICLE"
    STOLEN_VEHICLE = "STOLEN_VEHICLE"
    RECOVERED_VEHICLE = "RECOVERED_VEHICLE"
    VICTIM_VEHICLE = "VICTIM_VEHICLE"
    OTHER = "OTHER"


class Vehicle(Base, TimestampMixin):
    __tablename__ = "vehicles"

    id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        primary_key=True,
        default=uuid.uuid4
    )
    registration_number: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    vehicle_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    make: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    # Relationships
    case_associations: Mapped[List["CaseVehicle"]] = relationship(
        "CaseVehicle", back_populates="vehicle", cascade="all, delete-orphan"
    )


class CaseVehicle(Base, TimestampMixin):
    __tablename__ = "case_vehicles"
    __table_args__ = (
        UniqueConstraint("case_id", "vehicle_id", "role", name="uq_case_vehicle_role"),
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
    vehicle_id: Mapped[uuid.UUID] = mapped_column(
        GUID,
        ForeignKey("vehicles.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role: Mapped[VehicleRole] = mapped_column(
        Enum(VehicleRole, name="vehicle_role_enum", create_type=False),
        default=VehicleRole.OTHER,
        nullable=False
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="vehicle_associations")
    vehicle: Mapped["Vehicle"] = relationship("Vehicle", back_populates="case_associations")
