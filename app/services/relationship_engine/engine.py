from typing import List
from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.relationship_engine.attribute_relationships import (
    extract_attribute_relationship_signals,
)
from app.services.relationship_engine.case_relationships import (
    extract_case_relationship_signals,
)
from app.services.relationship_engine.models import (
    CaseRelationshipAnalysis,
    RelationshipSignal,
)
from app.services.relationship_engine.person_relationships import (
    extract_person_relationship_signals,
)


class RelationshipSignalEngine:
    """Unified Relationship Signal Extraction Engine for S.I.R.I.S. Central Intelligence Engine."""

    @classmethod
    def analyze_case_relationship(
        cls,
        c1: ExtractedCaseFeatures,
        c2: ExtractedCaseFeatures
    ) -> CaseRelationshipAnalysis:
        """Extracts all discrete relationship signals between two extracted case feature objects."""
        src_id = c1.identity.case_id
        tgt_id = c2.identity.case_id

        # Self Comparison Guard
        if src_id == tgt_id:
            return CaseRelationshipAnalysis(
                source_case_id=src_id,
                target_case_id=tgt_id,
                signals=[],
                summary_explanation="Self-comparison: Identical case record."
            )

        signals: List[RelationshipSignal] = []

        # 1. Person Relationships
        signals.extend(extract_person_relationship_signals(c1, c2))

        # 2. Attribute Relationships (Phone, Vehicle, Location)
        signals.extend(extract_attribute_relationship_signals(c1, c2))

        # 3. Case Characteristics Relationships (MO, Category, Legal, Temporal)
        signals.extend(extract_case_relationship_signals(c1, c2))

        if signals:
            types_str = ", ".join(sorted(list({s.relationship_type.value for s in signals})))
            summary = f"Identified {len(signals)} relationship signal(s): [{types_str}]."
        else:
            summary = "No relationship signals identified between cases."

        return CaseRelationshipAnalysis(
            source_case_id=src_id,
            target_case_id=tgt_id,
            signals=signals,
            summary_explanation=summary
        )
