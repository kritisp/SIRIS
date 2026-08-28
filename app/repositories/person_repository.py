import uuid
from typing import List, Optional
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload
from app.models.person import Person
from app.repositories.base import BaseRepository


class PersonRepository(BaseRepository[Person]):
    def __init__(self, session: Session):
        super().__init__(Person, session)

    def get_by_name(self, name: str, limit: int = 50) -> List[Person]:
        stmt = (
            select(Person)
            .where(Person.name.ilike(f"%{name}%"))
            .limit(limit)
        )
        return list(self.session.scalars(stmt).all())

    def get_by_identifier_hash(self, identifier_hash: str) -> Optional[Person]:
        stmt = select(Person).where(Person.identifier_hash == identifier_hash)
        return self.session.scalars(stmt).first()
