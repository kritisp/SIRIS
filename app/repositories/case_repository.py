import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models.case import Case
from app.repositories.base import BaseRepository


class CaseRepository(BaseRepository[Case]):
    def __init__(self, session: Session):
        super().__init__(Case, session)

    def get_by_fir_number(self, fir_number: str) -> Optional[Case]:
        stmt = (
            select(Case)
            .where(Case.fir_number == fir_number)
            .options(
                selectinload(Case.person_associations),
                selectinload(Case.evidences),
                selectinload(Case.investigation_events),
                selectinload(Case.legal_section_associations),
            )
        )
        return self.session.scalars(stmt).first()

    def get_by_district(self, district: str, limit: int = 50) -> List[Case]:
        stmt = select(Case).where(Case.district == district).limit(limit)
        return list(self.session.scalars(stmt).all())

    def get_by_crime_category(self, crime_category: str, limit: int = 50) -> List[Case]:
        stmt = select(Case).where(Case.crime_category == crime_category).limit(limit)
        return list(self.session.scalars(stmt).all())
