import math
from datetime import datetime
from app.config.settings import settings
from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.case_similarity.similarity.models import CaseSimilaritySignal, SignalStatus


def compute_temporal_similarity(
    c1: ExtractedCaseFeatures,
    c2: ExtractedCaseFeatures
) -> CaseSimilaritySignal:
    """Computes temporal proximity decay and time-of-day similarity."""
    w = settings.SIM_WEIGHT_TEMPORAL

    d_str1 = c1.temporal.incident_date or c1.identity.incident_date
    d_str2 = c2.temporal.incident_date or c2.identity.incident_date

    if not d_str1 or not d_str2:
        return CaseSimilaritySignal(
            signal_name="TEMPORAL_SIMILARITY",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Incident date unavailable on one or both cases."
        )

    try:
        dt1 = datetime.strptime(d_str1[:10], "%Y-%m-%d")
        dt2 = datetime.strptime(d_str2[:10], "%Y-%m-%d")
        days_diff = abs((dt1 - dt2).days)
    except ValueError:
        return CaseSimilaritySignal(
            signal_name="TEMPORAL_SIMILARITY",
            raw_score=0.0,
            weight=w,
            weighted_score=0.0,
            status=SignalStatus.UNAVAILABLE,
            evidence=[],
            explanation="Malformed incident date format."
        )

    decay_days = settings.TEMPORAL_DECAY_DAYS
    date_score = math.exp(-days_diff / decay_days)

    # Time-of-day boost if hour available on both
    tod1 = c1.temporal.time_of_day_bucket
    tod2 = c2.temporal.time_of_day_bucket
    tod_match = (tod1 and tod2 and tod1 == tod2)

    if tod_match:
        sim_score = min(1.0, date_score * 1.15)
    else:
        sim_score = date_score

    sim_score = round(sim_score, 4)

    if days_diff == 0:
        status = SignalStatus.MATCH
        qualifier = "SAME DAY"
    elif days_diff <= 7:
        status = SignalStatus.MATCH
        qualifier = f"{days_diff} DAYS APART"
    elif days_diff <= 30:
        status = SignalStatus.PARTIAL
        qualifier = f"{days_diff} DAYS APART"
    else:
        status = SignalStatus.MISMATCH
        qualifier = f"{days_diff} DAYS APART"

    evidence = [f"Cases occurred {qualifier}"]
    if tod_match:
        evidence.append(f"Matching time-of-day bucket: {tod1}")

    return CaseSimilaritySignal(
        signal_name="TEMPORAL_SIMILARITY",
        raw_score=sim_score,
        weight=w,
        weighted_score=round(sim_score * w, 4),
        status=status,
        evidence=evidence,
        explanation=f"Incident dates {days_diff} days apart with decay factor {decay_days} days."
    )
