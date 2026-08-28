import uuid
from typing import List
from sqlalchemy import select
from sqlalchemy.orm import Session
from app.models.investigation_event import InvestigationEvent
from app.repositories.base import BaseRepository


class InvestigationEventRepository(BaseRepository[InvestigationEvent]):
    def __init__(self, session: Session):
        super().__init__(InvestigationEvent, session)

    def get_by_case_id(self, case_id: uuid.UUID) -> List[InvestigationEvent]:
        stmt = (
            select(InvestigationEvent)
            .where(InvestigationEvent.case_id == case_id)
            .order_by(InvestigationEvent.event_date.asc())
        )
        return list(self.session.scalars(stmt).all())
