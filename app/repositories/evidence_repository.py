import uuid
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.evidence import Evidence, EvidenceType
from app.repositories.base import BaseRepository


class EvidenceRepository(BaseRepository[Evidence]):
    def __init__(self, session: Session):
        super().__init__(Evidence, session)

    def get_by_case_id(self, case_id: uuid.UUID) -> List[Evidence]:
        stmt = select(Evidence).where(Evidence.case_id == case_id)
        return list(self.session.scalars(stmt).all())

    def get_by_type(self, evidence_type: EvidenceType) -> List[Evidence]:
        stmt = select(Evidence).where(Evidence.evidence_type == evidence_type)
        return list(self.session.scalars(stmt).all())
