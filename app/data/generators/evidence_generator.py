import datetime
import random
from typing import List
from app.models.evidence import Evidence, EvidenceType
from app.models.investigation_event import InvestigationEvent, InvestigationEventType


def generate_case_evidences(rng: random.Random, case_id) -> List[Evidence]:
    """Generates 1 to 3 realistic evidence records for a given case."""
    evidences: List[Evidence] = []
    count = rng.randint(1, 3)

    types = [
        (EvidenceType.CCTV, "CCTV Footage showing suspect movement", "Traffic Camera"),
        (EvidenceType.MOBILE, "Call detail records (CDR) dump", "Telecom Service Provider"),
        (EvidenceType.VEHICLE, "Getaway vehicle tire track impression", "Crime Scene Unit"),
        (EvidenceType.WEAPON, "Iron rod / sharp weapon recovered near spot", "Investigating Officer"),
        (EvidenceType.DIGITAL, "Hard drive / transaction log export", "Cyber Crime Forensic Lab"),
        (EvidenceType.DOCUMENT, "Forged identity document copy", "Bank Branch Manager"),
        (EvidenceType.PHYSICAL, "Fingerprint impression sample", "Fingerprint Bureau"),
    ]

    for _ in range(count):
        etype, desc, src = rng.choice(types)
        ev = Evidence(
            case_id=case_id,
            evidence_type=etype,
            description=desc,
            source=src,
            collected_at=datetime.datetime.now(datetime.timezone.utc),
            status="COLLECTED",
        )
        evidences.append(ev)

    return evidences


def generate_case_investigation_events(rng: random.Random, case_id, reg_date: datetime.date) -> List[InvestigationEvent]:
    """Generates chronological investigation events for a case."""
    events: List[InvestigationEvent] = []

    dt1 = datetime.datetime.combine(reg_date, datetime.time(9, 0), tzinfo=datetime.timezone.utc)
    dt2 = dt1 + datetime.timedelta(days=rng.randint(1, 3))
    dt3 = dt2 + datetime.timedelta(days=rng.randint(3, 10))

    events.append(
        InvestigationEvent(
            case_id=case_id,
            event_type=InvestigationEventType.FIR_REGISTERED,
            description="FIR registered and copy dispatched to magistrate.",
            event_date=dt1,
            officer_reference="Inspector I/C",
        )
    )

    events.append(
        InvestigationEvent(
            case_id=case_id,
            event_type=InvestigationEventType.EVIDENCE_COLLECTED,
            description="Spot inspection conducted; evidence seizure memo prepared.",
            event_date=dt2,
            officer_reference="Sub-Inspector (SI)",
        )
    )

    if rng.random() > 0.5:
        events.append(
            InvestigationEvent(
                case_id=case_id,
                event_type=InvestigationEventType.SUSPECT_IDENTIFIED,
                description="Suspect identified through technical intelligence and informant network.",
                event_date=dt3,
                officer_reference="SI Lead Investigator",
            )
        )

    return events
