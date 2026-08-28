from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.relationship_engine.engine import RelationshipSignalEngine
from app.services.relationship_engine.models import CaseRelationshipAnalysis
from app.services.relationship_engine.confidence.aggregator import (
    aggregate_relationship_confidence,
)
from app.services.relationship_engine.confidence.models import (
    RelationshipConfidenceAssessment,
)


class RelationshipConfidenceEngine:
    """Unified Relationship Evidence Aggregation & Confidence Engine for S.I.R.I.S. Central Intelligence Engine."""

    @classmethod
    def evaluate_relationship_confidence(
        cls,
        c1: ExtractedCaseFeatures,
        c2: ExtractedCaseFeatures
    ) -> RelationshipConfidenceAssessment:
        """Extracts Step 5A relationship signals and aggregates them into a strongly typed relationship confidence assessment."""
        analysis = RelationshipSignalEngine.analyze_case_relationship(c1, c2)
        return cls.evaluate_from_analysis(analysis)

    @classmethod
    def evaluate_from_analysis(
        cls,
        analysis: CaseRelationshipAnalysis
    ) -> RelationshipConfidenceAssessment:
        """Aggregates an existing CaseRelationshipAnalysis object into a relationship confidence assessment."""
        return aggregate_relationship_confidence(
            source_case_id=analysis.source_case_id,
            target_case_id=analysis.target_case_id,
            signals=analysis.signals
        )
