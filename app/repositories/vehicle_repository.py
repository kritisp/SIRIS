import uuid
from typing import Optional
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.vehicle import Vehicle
from app.repositories.base import BaseRepository


class VehicleRepository(BaseRepository[Vehicle]):
    def __init__(self, session: Session):
        super().__init__(Vehicle, session)

    def get_by_registration_number(self, registration_number: str) -> Optional[Vehicle]:
        stmt = select(Vehicle).where(Vehicle.registration_number == registration_number)
        return self.session.scalars(stmt).first()
