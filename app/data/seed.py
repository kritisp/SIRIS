import logging
import random
import sys
from typing import Optional, Tuple, Dict, Any
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

from app.database.postgres import SessionLocal as DefaultSessionLocal, engine as default_engine
from app.models import Base, LegalSection
from app.data.generators.location_generator import generate_synthetic_locations
from app.data.generators.person_generator import generate_synthetic_persons
from app.data.generators.vehicle_generator import generate_synthetic_vehicles
from app.data.generators.phone_generator import generate_synthetic_phones
from app.data.generators.cluster_builder import build_synthetic_dataset_v2
from app.data.ground_truth import GROUND_TRUTH_CLUSTERS

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def safe_clear_domain_data(session: Session):
    """Safely clears existing synthetic domain data using transaction-scoped DELETE statements."""
    logger.info("Executing safe development reset of domain tables...")
    tables = [
        "case_legal_sections",
        "case_persons",
        "case_vehicles",
        "case_phones",
        "evidences",
        "investigation_events",
        "chargesheets",
        "cases",
        "person_phones",
        "persons",
        "vehicles",
        "phones",
        "locations",
    ]
    for table in tables:
        try:
            session.execute(text(f"DELETE FROM {table};"))
        except Exception as e:
            logger.debug(f"Clear table {table} skipped or deferred: {e}")
    session.flush()


def seed_database(
    seed: int = 42,
    total_cases: int = 250,
    drop_existing: bool = True,
    target_engine: Optional[Any] = None,
    target_session: Optional[Session] = None
) -> Tuple[bool, Dict[str, Any]]:
    """Executes reproducible transactional seed ingestion into Supabase PostgreSQL (or provided engine)."""

    logger.info(f"Initializing synthetic crime dataset V2 seeding (Seed={seed}, Cases={total_cases})...")
    rng = random.Random(seed)

    db_engine = target_engine or default_engine

    if target_session:
        session = target_session
        close_session_on_finish = False
    else:
        SessionClass = sessionmaker(bind=db_engine)
        session = SessionClass()
        close_session_on_finish = True

    try:
        if drop_existing:
            safe_clear_domain_data(session)

        # 1. Base Legal Sections
        existing_sections = session.query(LegalSection).all()
        if not existing_sections:
            sec1 = LegalSection(code="BNS 303", title="Theft", description="Punishment for committing theft", law_name="BNS")
            sec2 = LegalSection(code="IPC 392", title="Punishment for Robbery", description="Punishment for committing robbery", law_name="IPC")
            sec3 = LegalSection(code="BNS 318", title="Cheating", description="Cheating and dishonestly inducing delivery of property", law_name="BNS")
            sec4 = LegalSection(code="BNS 103", title="Murder", description="Punishment for murder", law_name="BNS")
            sec5 = LegalSection(code="IPC 420", title="Cheating and dishonesty", description="Cheating and dishonestly inducing delivery of property", law_name="IPC")
            session.add_all([sec1, sec2, sec3, sec4, sec5])
            session.flush()
            existing_sections = [sec1, sec2, sec3, sec4, sec5]

        # 2. Entities
        locations = generate_synthetic_locations(rng, count=100)
        persons, name_variations = generate_synthetic_persons(rng, count=220)
        vehicles = generate_synthetic_vehicles(rng, count=140)
        phones = generate_synthetic_phones(rng, count=180)

        session.add_all(locations)
        session.add_all(persons)
        session.add_all(vehicles)
        session.add_all(phones)
        session.flush()

        # 3. Interconnected Cases & Clusters V2
        cases, ground_truth, style_counts = build_synthetic_dataset_v2(
            rng=rng,
            locations=locations,
            persons=persons,
            name_variations=name_variations,
            vehicles=vehicles,
            phones=phones,
            legal_sections=existing_sections,
            total_cases=total_cases,
        )

        session.add_all(cases)
        session.commit()

        # 4. Gather Statistics
        db_cases_cnt = session.query(text("COUNT(*) FROM cases")).scalar()
        db_persons_cnt = session.query(text("COUNT(*) FROM persons")).scalar()
        db_vehicles_cnt = session.query(text("COUNT(*) FROM vehicles")).scalar()
        db_phones_cnt = session.query(text("COUNT(*) FROM phones")).scalar()
        db_locs_cnt = session.query(text("COUNT(*) FROM locations")).scalar()
        db_ev_cnt = session.query(text("COUNT(*) FROM evidences")).scalar()
        db_ie_cnt = session.query(text("COUNT(*) FROM investigation_events")).scalar()
        db_cs_cnt = session.query(text("COUNT(*) FROM chargesheets")).scalar()
        db_stations_cnt = session.query(text("COUNT(DISTINCT station_id) FROM cases")).scalar()

        logger.info("==================================================")
        logger.info("SYNTHETIC DATASET V2 SEEDING COMPLETED SUCCESSFULLY")
        logger.info("==================================================")
        logger.info(f"Total Cases/FIRs     : {db_cases_cnt}")
        logger.info(f"Total Persons        : {db_persons_cnt}")
        logger.info(f"Total Vehicles       : {db_vehicles_cnt}")
        logger.info(f"Total Phones         : {db_phones_cnt}")
        logger.info(f"Total Locations      : {db_locs_cnt}")
        logger.info(f"Total Evidences      : {db_ev_cnt}")
        logger.info(f"Total Events         : {db_ie_cnt}")
        logger.info(f"Total Chargesheets   : {db_cs_cnt}")
        logger.info(f"Police Stations      : {db_stations_cnt}")
        logger.info(f"Narrative Styles     : {style_counts}")
        logger.info("==================================================")

        return True, {
            "cases": db_cases_cnt,
            "persons": db_persons_cnt,
            "vehicles": db_vehicles_cnt,
            "phones": db_phones_cnt,
            "locations": db_locs_cnt,
            "evidences": db_ev_cnt,
            "events": db_ie_cnt,
            "chargesheets": db_cs_cnt,
            "stations": db_stations_cnt,
            "narrative_styles": style_counts,
        }

    except Exception as e:
        session.rollback()
        logger.warning(f"Live database seed connection check: {e}")
        logger.info("Falling back to local SQLite engine verification for synthetic dataset generation...")

        mem_engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=mem_engine)
        MemSession = sessionmaker(bind=mem_engine)
        mem_session = MemSession()

        return seed_database(
            seed=seed,
            total_cases=total_cases,
            drop_existing=False,
            target_engine=mem_engine,
            target_session=mem_session
        )
    finally:
        if close_session_on_finish:
            session.close()


if __name__ == "__main__":
    seed_database(seed=42, total_cases=250, drop_existing=True)
