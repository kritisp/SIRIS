from app.services.case_similarity.models import ExtractedCaseFeatures
from app.services.case_similarity.similarity.models import CaseSimilarityResult
from app.services.case_similarity.similarity.text_similarity import (
    compute_crime_category_similarity,
    compute_mo_text_similarity,
)
from app.services.case_similarity.similarity.legal_similarity import (
    compute_legal_section_similarity,
)
from app.services.case_similarity.similarity.geographic_similarity import (
    compute_geographic_similarity,
)
from app.services.case_similarity.similarity.temporal_similarity import (
    compute_temporal_similarity,
)
from app.services.case_similarity.similarity.entity_similarity import (
    compute_person_overlap_similarity,
    compute_vehicle_overlap_similarity,
    compute_phone_overlap_similarity,
)
from app.services.case_similarity.similarity.scoring import compute_case_similarity_score


class CaseSimilarityEngine:
    """Deterministic, multi-signal Case Similarity Engine for S.I.R.I.S. Central Intelligence Engine."""

    @classmethod
    def compare_cases(
        cls,
        c1: ExtractedCaseFeatures,
        c2: ExtractedCaseFeatures
    ) -> CaseSimilarityResult:
        """Evaluates pairwise multi-signal similarity between two extracted case feature objects."""
        source_id = c1.identity.case_id
        candidate_id = c2.identity.case_id

        # Compute individual signals
        signals = [
            compute_mo_text_similarity(c1, c2),
            compute_crime_category_similarity(c1, c2),
            compute_legal_section_similarity(c1, c2),
            compute_geographic_similarity(c1, c2),
            compute_temporal_similarity(c1, c2),
            compute_person_overlap_similarity(c1, c2),
            compute_vehicle_overlap_similarity(c1, c2),
            compute_phone_overlap_similarity(c1, c2),
        ]

        # Aggregate weighted score & determine similarity level
        return compute_case_similarity_score(source_id, candidate_id, signals)
