from typing import List, Tuple
from app.config.settings import settings
from app.services.relationship_engine.models import RelationshipSignal, RelationshipType, SignalCertainty
from app.services.relationship_engine.confidence.family_grouping import (
    get_signal_base_weight,
    group_signals_by_family,
)
from app.services.relationship_engine.confidence.models import (
    RelationshipConfidenceAssessment,
    RelationshipConfidenceLevel,
    SignalFamily,
)


def aggregate_relationship_confidence(
    source_case_id: str,
    target_case_id: str,
    signals: List[RelationshipSignal]
) -> RelationshipConfidenceAssessment:
    """Aggregates Step 5A relationship signals into an evidence-backed relationship confidence assessment."""

    # 1. Handle Self-Comparison
    if source_case_id == target_case_id:
        return RelationshipConfidenceAssessment(
            source_case_id=source_case_id,
            target_case_id=target_case_id,
            confidence_score=1.0,
            confidence_level=RelationshipConfidenceLevel.SELF_COMPARISON,
            contributing_signals=signals,
            evidence_summary="Self-comparison: Identical case record.",
            explanation="SELF_COMPARISON (Score: 1.00). Source and target case are identical.",
            uncertainty_notes=[],
            provenance="Step 5A Relationship Signals",
            methodology_version="relationship-confidence-v1"
        )

    # 2. Handle Empty / No Signals
    if not signals:
        return RelationshipConfidenceAssessment(
            source_case_id=source_case_id,
            target_case_id=target_case_id,
            confidence_score=0.0,
            confidence_level=RelationshipConfidenceLevel.INSUFFICIENT_DATA,
            contributing_signals=[],
            evidence_summary="No relationship signals identified between cases.",
            explanation="INSUFFICIENT_DATA (Score: 0.00). No evidence signals connect these case records.",
            uncertainty_notes=["Insufficient evidentiary connections between cases."],
            provenance="Step 5A Relationship Signals",
            methodology_version="relationship-confidence-v1"
        )

    # 3. Categorize Signals by Certainty
    high_sigs: List[RelationshipSignal] = []
    poss_sigs: List[RelationshipSignal] = []
    weak_sigs: List[RelationshipSignal] = []
    uncertainty_notes: List[str] = []
    conflict_notes: List[str] = []

    for s in signals:
        if s.certainty == SignalCertainty.HIGH_CONFIDENCE:
            high_sigs.append(s)
        elif s.certainty == SignalCertainty.POSSIBLE:
            poss_sigs.append(s)
        else:
            weak_sigs.append(s)

        if s.uncertainty_note:
            uncertainty_notes.append(s.uncertainty_note)

    # 4. Group by Family & Calculate Base Family Score
    grouped = group_signals_by_family(signals)
    contributing_families = sorted(list(grouped.keys()), key=lambda f: f.value)

    # Find maximum primary family contribution to establish base evidence strength
    family_scores: List[float] = []
    for fam, items in grouped.items():
        fam_sum = 0.0
        for sig, factor in items:
            bw = get_signal_base_weight(sig.relationship_type)
            fam_sum += bw * sig.raw_score * factor
        family_scores.append(fam_sum)

    family_scores.sort(reverse=True)
    primary_family_score = family_scores[0] if family_scores else 0.0
    secondary_family_score_sum = sum(family_scores[1:]) if len(family_scores) > 1 else 0.0

    # Base score combines primary family strength + discounted secondary families
    base_score = 0.70 * primary_family_score + 0.30 * secondary_family_score_sum

    # 5. Independent Family Bonus (Rewards corroboration across distinct evidence categories)
    num_families = len(contributing_families)
    family_bonus = 0.0
    if num_families >= 2:
        family_bonus += 0.15
    if num_families >= 3:
        family_bonus += 0.10
    if num_families >= 4:
        family_bonus += (num_families - 3) * 0.05

    # 6. Conflict / Caution Penalties
    conflict_penalty = 0.0
    has_high_person = any(s.relationship_type == RelationshipType.SHARED_HIGH_CONFIDENCE_PERSON for s in signals)
    has_unverified_name = any(s.uncertainty_note and "unverified identity" in s.uncertainty_note for s in signals)

    if has_unverified_name and not has_high_person:
        conflict_penalty += 0.10
        conflict_notes.append("Person identity relies on name-only match without supporting DOB/phone evidence.")

    raw_score = base_score + family_bonus - conflict_penalty

    # 7. Contextual Cap Rule
    # If ONLY behavioral, legal, or temporal signals are present without direct entity/attribute overlap, cap at 0.45
    direct_entity_families = {SignalFamily.PERSON_IDENTITY, SignalFamily.CONTACT, SignalFamily.VEHICLE, SignalFamily.LOCATION}
    has_direct_evidence = bool(set(contributing_families) & direct_entity_families)

    if not has_direct_evidence:
        raw_score = min(0.45, raw_score)
        uncertainty_notes.append("Only contextual similarity signals present; no direct entity or attribute overlaps.")

    final_score = round(min(1.0, max(0.0, raw_score)), 4)

    # 8. Evaluate Confidence Level
    if final_score >= settings.REL_THRESH_VERY_HIGH:
        level = RelationshipConfidenceLevel.VERY_HIGH
    elif final_score >= settings.REL_THRESH_HIGH:
        level = RelationshipConfidenceLevel.HIGH
    elif final_score >= settings.REL_THRESH_MODERATE:
        level = RelationshipConfidenceLevel.MODERATE
    elif final_score >= settings.REL_THRESH_LOW:
        level = RelationshipConfidenceLevel.LOW
    else:
        level = RelationshipConfidenceLevel.INSUFFICIENT_DATA

    # 9. Generate Deterministic Summary & Explanation
    ev_summary_parts = []
    if high_sigs:
        ev_summary_parts.append(f"{len(high_sigs)} high-confidence signal(s)")
    if poss_sigs:
        ev_summary_parts.append(f"{len(poss_sigs)} possible signal(s)")
    if weak_sigs:
        ev_summary_parts.append(f"{len(weak_sigs)} weak signal(s)")

    ev_summary = f"{level.value} confidence based on " + ", ".join(ev_summary_parts) + f" across {len(contributing_families)} evidence categories."

    explanation_parts = [f"Relationship Confidence: {level.value} (Score: {final_score:.2f})."]
    explanation_parts.append(f"Contributing Evidence Categories ({len(contributing_families)}): {', '.join([f.value for f in contributing_families])}.")
    if conflict_notes:
        explanation_parts.append(f"Cautionary Factors: {' | '.join(conflict_notes)}")

    explanation = " ".join(explanation_parts)

    return RelationshipConfidenceAssessment(
        source_case_id=source_case_id,
        target_case_id=target_case_id,
        confidence_score=final_score,
        confidence_level=level,
        contributing_signals=signals,
        high_confidence_signals=high_sigs,
        possible_signals=poss_sigs,
        weak_signals=weak_sigs,
        conflicting_or_cautionary_signals=conflict_notes,
        contributing_families=contributing_families,
        evidence_summary=ev_summary,
        explanation=explanation,
        uncertainty_notes=list(set(uncertainty_notes)),
        provenance="Step 5A Relationship Signals",
        methodology_version="relationship-confidence-v1"
    )
