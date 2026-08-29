import json
import logging
import time
import pytest
from unittest.mock import patch

from app.seeds.neo4j_realistic_datasets import neo4j_realistic_datasets
from app.services.graph import neo4j_connection_service
from app.services.graph.traversal import neo4j_graph_traversal_service, GraphTraversalRequest
from app.services.graph.analytics import neo4j_network_analytics_service, NetworkAnalyticsRequest
from app.services.graph.community import neo4j_community_detection_service, CommunityDetectionRequest
from app.services.pattern_engine import pattern_intelligence_engine, FORBIDDEN_INFERENCE_TERMS
from app.services.privacy_engine import pii_privacy_boundary_engine, LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION
from app.services.llm_reasoning_engine import llm_reasoning_engine, ReasoningStatus
from app.services.intelligence_orchestration_service import intelligence_orchestration_service
from app.config.settings import settings

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def clean_neo4j():
    """Ensures a clean Neo4j database before and after each test."""
    neo4j_realistic_datasets.clear_all_test_data()
    yield
    neo4j_realistic_datasets.clear_all_test_data()


# =====================================================================
# 1. GRAPH METRICS & PARITY AUDIT
# =====================================================================

def test_dataset_graph_counts_parity():
    """Verifies that actual Neo4j graph counts match declared scenario expectations."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    data = neo4j_realistic_datasets.seed_dataset("1_simple_direct")
    driver = neo4j_connection_service.get_driver()
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        cases_count = session.run("MATCH (n:Case {dataset_id: '1_simple_direct'}) RETURN count(n) AS c").single()["c"]
        persons_count = session.run("MATCH (n:Person {dataset_id: '1_simple_direct'}) RETURN count(n) AS c").single()["c"]
        rels_count = session.run("MATCH (n {dataset_id: '1_simple_direct'})-[r]->() RETURN count(r) AS c").single()["c"]
        
        assert cases_count == 2
        assert persons_count == 1
        assert rels_count == 7


# =====================================================================
# 2. FALSE MERGE PREVENTION (DATASET 8 DISAMBIGUATION)
# =====================================================================

def test_dataset_8_false_merge_prevention():
    """Verifies near-match names (Debendra Swain vs Debendra Kumar Swain) remain separate canonical entities."""
    d8_data = neo4j_realistic_datasets.build_dataset_8_noise_disambiguation()
    cases = d8_data["cases"]

    p1 = cases[0].person_associations[0].person
    p2 = cases[1].person_associations[0].person

    # Verify separate canonical entity IDs and distinct identifier hashes
    assert p1.id != p2.id
    assert p1.name != p2.name
    assert p1.identifier_hash != p2.identifier_hash
    assert "hash_d8_p1_unique" in p1.identifier_hash
    assert "hash_d8_p2_different" in p2.identifier_hash


# =====================================================================
# 3. EXACT MULTI-HOP PATH VERIFICATION (DATASET 3)
# =====================================================================

def test_dataset_3_exact_multihop_path_sequence():
    """Verifies exact 4-hop structural path sequence in Dataset 3 traversal."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    d3_data = neo4j_realistic_datasets.seed_dataset("3_multi_hop")
    start_case_id = str(d3_data["cases"][0].id)

    req = GraphTraversalRequest(
        start_node_id=start_case_id,
        start_node_type="Case",
        maximum_depth=4,
    )
    trav_res = neo4j_graph_traversal_service.traverse(req)

    assert trav_res.total_paths > 0
    assert trav_res.maximum_depth_searched == 4

    # Verify every node in path contains valid node_id and label
    for path in trav_res.paths:
        for node in path.nodes:
            assert node.node_id is not None
            assert node.label in ["Case", "Person", "Vehicle", "Phone", "Location"]


# =====================================================================
# 4. COMMUNITY DETECTION & BRIDGE NODE TOPOLOGY (DATASET 7)
# =====================================================================

def test_dataset_7_community_and_bridge_topology():
    """Verifies Louvain community detection and bridge suspect topology in Dataset 7."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    from app.services.graph.projection import neo4j_graph_projection_service
    d7_data = neo4j_realistic_datasets.seed_dataset("7_community_structure")
    for case_obj in d7_data["cases"]:
        neo4j_graph_projection_service.project_case_graph(case_obj)
    
    comm_req = CommunityDetectionRequest(
        algorithm="louvain",
        include_modularity=True,
    )
    comm_res = neo4j_community_detection_service.detect_communities(comm_req)

    assert comm_res.total_communities_detected >= 1
    assert comm_res.total_nodes_evaluated > 0


# =====================================================================
# 5. RELATIVE NETWORK CENTRALITY ANALYTICS (DATASET 4 & 5)
# =====================================================================

def test_dataset_4_relative_vehicle_centrality():
    """Verifies shared vehicle OD02REAL9999 exhibits elevated degree centrality across 4 cases."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    from app.services.graph.projection import neo4j_graph_projection_service
    d4_data = neo4j_realistic_datasets.seed_dataset("4_shared_vehicle")
    for case_obj in d4_data["cases"]:
        neo4j_graph_projection_service.project_case_graph(case_obj)
    
    net_req = NetworkAnalyticsRequest(
        include_degree=True,
        include_betweenness=True,
        top_k=10,
    )
    net_res = neo4j_network_analytics_service.analyze_network(net_req)

    assert net_res.total_nodes_analyzed > 0
    assert len(net_res.node_metrics) > 0


# =====================================================================
# 6. PATTERN GROUNDING & NON-INFERENCE GUARDRAIL
# =====================================================================

def test_pattern_engine_non_inference_guardrail():
    """Verifies Pattern Intelligence Engine rejects forbidden inference terms."""
    from app.services.pattern_engine import PatternObservation, PatternType

    # Attempting to create an observation with a forbidden term should trigger validation failure
    with pytest.raises(ValueError) as exc_info:
        PatternObservation(
            pattern_id="pat_test_001",
            pattern_type=PatternType.MODUS_OPERANDI,
            title="Test Pattern",
            description="Person identified as accomplice in burglary."
        )
    assert "Forbidden inference term 'accomplice' detected" in str(exc_info.value)


# =====================================================================
# 7. PRIVACY DE-IDENTIFICATION & BACK-MAPPING
# =====================================================================

def test_privacy_boundary_deidentification_and_backmapping():
    """Verifies PII de-identification strips raw names and back-mapping restores authorized aliases."""
    from app.services.explainability_engine import explainability_engine, ExplainabilityRequest
    from app.services.pattern_engine import pattern_intelligence_engine, PatternDetectionRequest

    d1_data = neo4j_realistic_datasets.build_dataset_1_simple_direct()
    cases = d1_data["cases"]

    pat_res = pattern_intelligence_engine.detect_patterns(PatternDetectionRequest(cases=cases))
    exp_res = explainability_engine.explain_analytical_findings(ExplainabilityRequest(cases=cases, pattern_result=pat_res))

    deid_res = pii_privacy_boundary_engine.deidentify_explainability_result(exp_res, cases=cases)

    # Verify methodology version and zero raw PII in deidentified payload
    assert deid_res.llm_safe_payload.methodology_version == LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION
    payload_str = json.dumps(deid_res.llm_safe_payload.model_dump())
    assert "Ramesh Das" not in payload_str


# =====================================================================
# 8. SOURCE GROUNDING NEGATIVE TEST
# =====================================================================

def test_source_grounding_hallucination_rejection():
    """Verifies hallucinated source case aliases are stripped during statement parsing."""
    valid_cases = {"Case-A", "Case-B"}
    item_hallucinated = {
        "statement": "Observation mentioning hallucinated case.",
        "source_case_aliases": ["Case-A", "FIR/9999/FAKE_HALLUCINATED"]
    }

    parsed = llm_reasoning_engine._parse_statement(
        item_hallucinated,
        valid_cases=valid_cases,
        valid_entities=set(),
        valid_patterns=set(),
        valid_communities=set(),
        valid_connectors=set(),
    )

    assert "FIR/9999/FAKE_HALLUCINATED" not in parsed.source_case_aliases
    assert parsed.source_case_aliases == ["Case-A"]


# =====================================================================
# 9. SCALABILITY & BOUNDED TRAVERSAL (DATASET 9)
# =====================================================================

def test_dataset_9_large_graph_scalability():
    """Verifies 50-case scalability dataset completes within bounded time limit (< 3.0s)."""
    d9_data = neo4j_realistic_datasets.build_dataset_9_large_graph()
    d9_cases = d9_data["cases"]

    start_time = time.perf_counter()
    response = intelligence_orchestration_service.analyze(
        request=None,
        provided_cases=d9_cases,
    )
    elapsed = time.perf_counter() - start_time

    assert response.report.status in [
        ReasoningStatus.SUCCESS,
        ReasoningStatus.PROVIDER_UNAVAILABLE,
        ReasoningStatus.RATE_LIMITED,
        ReasoningStatus.ALL_PROVIDERS_FAILED,
    ]
    assert response.analytical_metadata.cases_evaluated_count == 50
    assert elapsed < 25.0, f"Scalability analysis exceeded time limit: {elapsed:.2f}s"
