import json
import logging
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app
from app.seeds.neo4j_realistic_datasets import neo4j_realistic_datasets
from app.services.graph import neo4j_connection_service
from app.services.intelligence_orchestration_service import intelligence_orchestration_service
from app.services.llm_reasoning_engine import GroqLLMClient, ReasoningStatus
from app.config.settings import settings

logger = logging.getLogger(__name__)

client = TestClient(app)


@pytest.fixture
def neo4j_realistic_fixture():
    """Fixtures and seeds all 10 realistic Neo4j test datasets if Neo4j is online, or returns synthetic datasets for in-memory execution."""
    health = neo4j_connection_service.check_health()
    is_live = (health.status == "UP")

    if is_live:
        seeded_data = neo4j_realistic_datasets.seed_all()
    else:
        seeded_data = {
            k: gen() for k, gen in neo4j_realistic_datasets.dataset_generators.items()
        }

    yield {"seeded_data": seeded_data, "is_live": is_live}

    if is_live:
        neo4j_realistic_datasets.clear_all_test_data()
        driver = neo4j_connection_service.get_driver()
        with driver.session(database=settings.NEO4J_DATABASE) as session:
            nodes_left = session.run("MATCH (n) RETURN count(n) AS c").single()["c"]
            rels_left = session.run("MATCH ()-[r]->() RETURN count(r) AS c").single()["c"]
            assert nodes_left == 0, f"Neo4j cleanup failed: {nodes_left} nodes remaining!"
            assert rels_left == 0, f"Neo4j cleanup failed: {rels_left} relationships remaining!"


def _make_analyze_wrapper(target_cases):
    """Wraps intelligence_orchestration_service.analyze to supply in-memory synthetic case models."""
    original_analyze = intelligence_orchestration_service.analyze
    def side_effect(request, provided_cases=None, db_session=None):
        return original_analyze(request, provided_cases=provided_cases or target_cases, db_session=db_session)
    return side_effect


# =====================================================================
# 1. DATASET 1 (DIRECT LINK) API TEST
# =====================================================================

def test_api_dataset_1_simple_direct_link(neo4j_realistic_fixture):
    """Tests POST /api/v1/intelligence/analyze for Dataset 1 (Direct Link)."""
    d1_data = neo4j_realistic_fixture["seeded_data"]["1_simple_direct"]
    d1_cases = d1_data["cases"]

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (
            json.dumps({
                "summary": "Direct cross-case association detected between Saheed Nagar PS cases.",
                "key_observations": [
                    {
                        "statement": "Person-A was identified across FIR/2026/D1_001 and FIR/2026/D1_002.",
                        "source_case_aliases": ["Case-A", "Case-B"]
                    }
                ],
                "recommended_followups": [
                    {"statement": "Review FIR/2026/D1_001 property recovery notes."}
                ],
                "limitations": ["Structural findings require investigator verification."]
            }),
            ReasoningStatus.SUCCESS,
            None,
        )

        with patch.object(intelligence_orchestration_service, "analyze", side_effect=_make_analyze_wrapper(d1_cases)):
            res = client.post(
                "/api/v1/intelligence/analyze",
                json={
                    "target_case_ids": [c.fir_number for c in d1_cases],
                    "analytical_scope": "FULL",
                    "max_cases": 10,
                },
            )

    assert res.status_code == 200
    body = res.json()
    assert body["report"]["status"] == "SUCCESS"
    assert body["analytical_metadata"]["cases_evaluated_count"] == 2


# =====================================================================
# 2. DATASET 2 (CROSS-STATION LINK) API TEST
# =====================================================================

def test_api_dataset_2_cross_station_link(neo4j_realistic_fixture):
    """Tests POST /api/v1/intelligence/analyze for Dataset 2 (3 Stations Linked by Suspect)."""
    d2_data = neo4j_realistic_fixture["seeded_data"]["2_cross_station"]
    d2_cases = d2_data["cases"]

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (
            json.dumps({
                "summary": "Cross-station activity detected spanning Saheed Nagar, Cuttack City, and Puri Sea Beach PS.",
                "key_observations": [
                    {
                        "statement": "Person-A linked across 3 police station jurisdictions.",
                        "source_case_aliases": ["Case-A", "Case-B", "Case-C"]
                    }
                ],
                "recommended_followups": [{"statement": "Coordinate cross-station investigative timeline."}],
                "limitations": ["Empirical association."]
            }),
            ReasoningStatus.SUCCESS,
            None,
        )

        with patch.object(intelligence_orchestration_service, "analyze", side_effect=_make_analyze_wrapper(d2_cases)):
            res = client.post(
                "/api/v1/intelligence/analyze",
                json={
                    "target_case_ids": [c.fir_number for c in d2_cases],
                    "target_station_ids": ["PS_BBSR_001", "PS_CTC_002", "PS_PURI_003"],
                    "analytical_scope": "CROSS_STATION",
                },
            )

    assert res.status_code == 200
    body = res.json()
    assert body["analytical_metadata"]["stations_involved_count"] == 3


# =====================================================================
# 3. DATASET 3 (MULTI-HOP PATH VERIFICATION) API TEST
# =====================================================================

def test_api_dataset_3_multi_hop_path_verification(neo4j_realistic_fixture):
    """Tests discovery and extraction of 4-hop structural paths via API."""
    d3_data = neo4j_realistic_fixture["seeded_data"]["3_multi_hop"]
    d3_cases = d3_data["cases"]

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (
            json.dumps({"summary": "Multi-hop path identified.", "key_observations": []}),
            ReasoningStatus.SUCCESS,
            None,
        )

        with patch.object(intelligence_orchestration_service, "analyze", side_effect=_make_analyze_wrapper(d3_cases)):
            res = client.post(
                "/api/v1/intelligence/analyze",
                json={
                    "target_case_ids": [c.fir_number for c in d3_cases],
                    "max_traversal_depth": 4,
                    "analytical_scope": "MULTI_HOP",
                },
            )

    assert res.status_code == 200
    body = res.json()
    assert "multi_hop_paths" in body
    assert body["analytical_metadata"]["traversal_depth_used"] == 4


# =====================================================================
# 4. DATASET 10 (PRIMARY DEMONSTRATION COMPLEX MULTI-STATION) API TEST
# =====================================================================

def test_api_dataset_10_complex_multistation_demonstration(neo4j_realistic_fixture):
    """Tests primary demonstration scenario across 5 stations, 20 cases, communities, and back-mapping."""
    d10_data = neo4j_realistic_fixture["seeded_data"]["10_complex_multistation"]
    d10_cases = d10_data["cases"]

    with patch.object(GroqLLMClient, "call_provider") as mock_groq:
        mock_groq.return_value = (
            json.dumps({
                "summary": "Primary demonstration: Complex multi-station burglary & theft structural pattern identified.",
                "key_observations": [
                    {
                        "statement": "Person-A identified across multiple police station jurisdictions with Vehicle-A.",
                        "source_case_aliases": ["Case-A", "Case-B"]
                    }
                ],
                "recommended_followups": [
                    {"statement": "Investigating officers across PS_BBSR_001 and PS_CTC_002 may share timeline logs."}
                ],
                "limitations": ["Empirical structural graph analysis."]
            }),
            ReasoningStatus.SUCCESS,
            None,
        )

        with patch.object(intelligence_orchestration_service, "analyze", side_effect=_make_analyze_wrapper(d10_cases)):
            res = client.post(
                "/api/v1/intelligence/analyze",
                json={
                    "target_case_ids": [c.fir_number for c in d10_cases],
                    "analytical_scope": "FULL",
                    "max_cases": 50,
                    "workspace_context": {
                        "investigator_id": "OFFICER_HEADQUARTERS",
                        "role": "CHIEF_INVESTIGATOR",
                        "workspace_id": "WS_DEMO_2026"
                    }
                },
            )

    assert res.status_code == 200
    body = res.json()
    assert body["report"]["status"] == "SUCCESS"
    assert body["analytical_metadata"]["cases_evaluated_count"] == 20
    assert body["analytical_metadata"]["stations_involved_count"] == 5
    assert body["analytical_metadata"]["authorization_context_applied"] is True

    # Verify back-mapping restored human readable name
    assert any(name in body["report"]["key_observations"][0]["statement"] for name in ["Synthetic Suspect D10 (Debendra Swain)", "Synthetic Associate D10 (Subhash Chandra)"])


# =====================================================================
# 5. API SAFETY BOUNDS & REQUEST VALIDATION
# =====================================================================

def test_api_request_validation_safety_caps():
    """Verifies API caps max_cases <= 100 and max_traversal_depth <= 5."""
    res_cases = client.post("/api/v1/intelligence/analyze", json={"max_cases": 200})
    assert res_cases.status_code == 422

    res_depth = client.post("/api/v1/intelligence/analyze", json={"max_traversal_depth": 10})
    assert res_depth.status_code == 422


# =====================================================================
# 6. EMPTY RESULT HANDLING
# =====================================================================

def test_api_empty_search_result_handling():
    """Verifies safe empty report when no matching cases are found."""
    res = client.post(
        "/api/v1/intelligence/analyze",
        json={"target_case_ids": ["FIR/NON_EXISTENT_999"]},
    )
    assert res.status_code == 200
    body = res.json()
    assert body["analytical_metadata"]["cases_evaluated_count"] == 0
    assert "Zero matching cases" in body["report"]["summary"]
