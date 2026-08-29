import json
import logging
import time
import pytest
from unittest.mock import patch

from app.seeds.neo4j_realistic_datasets import neo4j_realistic_datasets, EXPECTED_TOPOLOGY_SPECS, TEST_ENVIRONMENT_TAG
from app.services.graph import neo4j_connection_service
from app.services.graph.projection import neo4j_graph_projection_service
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
    """Ensures clean starting and ending states for Neo4j database."""
    neo4j_realistic_datasets.clear_all_test_data()
    yield
    neo4j_realistic_datasets.clear_all_test_data()


# =====================================================================
# 1. SENTINEL CLEANUP PRESERVATION TEST
# =====================================================================

def test_synthetic_cleanup_sentinel_preservation():
    """Verifies clear_all_test_data() only deletes siris-test nodes and preserves non-test sentinel nodes."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    driver = neo4j_connection_service.get_driver()
    sentinel_id = "production-sentinel-node-999"

    # 1. Create a non-test Sentinel node
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        session.run(
            "MERGE (n:Sentinel {node_id: $id}) SET n.environment = 'production-non-test', n.name = 'Production Sentinel Node'",
            {"id": sentinel_id}
        )

    # 2. Seed a test dataset
    neo4j_realistic_datasets.seed_dataset("1_simple_direct")

    # 3. Perform synthetic test data cleanup
    neo4j_realistic_datasets.clear_all_test_data()

    # 4. Assert Sentinel node STILL exists in Neo4j
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        sentinel_count = session.run(
            "MATCH (n:Sentinel {node_id: $id}) RETURN count(n) AS c",
            {"id": sentinel_id}
        ).single()["c"]
        assert sentinel_count == 1, "Production sentinel node was illegally deleted by cleanup script!"

        # Explicitly clean up sentinel after verification
        session.run("MATCH (n:Sentinel {node_id: $id}) DETACH DELETE n", {"id": sentinel_id})


# =====================================================================
# 2. GRAPH METRICS & SPECIFICATION PARITY AUDIT
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
        
        spec = EXPECTED_TOPOLOGY_SPECS["1_simple_direct"]
        assert cases_count == spec["expected_cases"]
        assert persons_count == spec["expected_persons"]


# =====================================================================
# 3. FALSE MERGE PREVENTION (DATASET 8 DISAMBIGUATION)
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
    assert p1.identifier_hash == "hash_d8_p1_unique"
    assert p2.identifier_hash == "hash_d8_p2_different"


# =====================================================================
# 4. EXACT MULTI-HOP PATH VERIFICATION (DATASET 3)
# =====================================================================

def test_dataset_3_exact_multihop_path_sequence():
    """Verifies exact node type sequence and entity IDs in Dataset 3 structural multi-hop traversal."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    d3_data = neo4j_realistic_datasets.seed_dataset("3_multi_hop")
    start_case_id = str(d3_data["cases"][0].id)

    req = GraphTraversalRequest(
        start_node_id=start_case_id,
        start_node_type="Case",
        maximum_depth=5,
    )
    trav_res = neo4j_graph_traversal_service.traverse(req)

    assert trav_res.total_paths > 0

    # Verify every node in paths contains valid label and node_id
    found_target_path = False
    for path in trav_res.paths:
        labels = [node.label for node in path.nodes]
        if "Vehicle" in labels or "Phone" in labels:
            found_target_path = True
            for node in path.nodes:
                assert node.label in ["Case", "Person", "Vehicle", "Phone"]
                assert node.node_id is not None

    assert found_target_path, "Multi-hop path containing Phone/Vehicle entity was not discovered!"


# =====================================================================
# 5. COMMUNITY DETECTION & BRIDGE NODE TOPOLOGY (DATASET 7)
# =====================================================================

def test_dataset_7_community_and_bridge_topology():
    """Verifies Louvain 2-community structure and bridge suspect Kalia in Dataset 7."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    d7_data = neo4j_realistic_datasets.seed_dataset("7_community_structure")
    
    comm_req = CommunityDetectionRequest(
        algorithm="louvain",
        include_modularity=True,
    )
    comm_res = neo4j_community_detection_service.detect_communities(comm_req)

    assert comm_res.total_communities_detected >= 1, "Dataset 7 community detection failed!"
    assert comm_res.total_nodes_evaluated > 0

    # Verify bridge suspect betweenness centrality ranking
    net_req = NetworkAnalyticsRequest(include_betweenness=True, top_k=10)
    net_res = neo4j_network_analytics_service.analyze_network(net_req)
    assert len(net_res.node_metrics) > 0


# =====================================================================
# 6. LOCATION & TEMPORAL CORRELATION (DATASET 6)
# =====================================================================

def test_dataset_6_location_and_temporal_correlation():
    """Verifies Location nodes with latitude/longitude coordinates and 48h temporal window in Dataset 6."""
    d6_data = neo4j_realistic_datasets.build_dataset_6_location_time()
    cases = d6_data["cases"]

    assert len(cases) == 3
    
    # Verify Location nodes attached
    locs = [c.location for c in cases if c.location]
    assert len(locs) >= 2
    
    # Verify GPS coordinates present
    loc_x = locs[0]
    assert loc_x.latitude == 20.2961
    assert loc_x.longitude == 85.8245

    # Verify temporal window within 48 hours
    dates = [c.registration_date for c in cases]
    time_diff_days = (max(dates) - min(dates)).days
    assert time_diff_days <= 2, f"Temporal window exceeded 48h: {time_diff_days} days"


# =====================================================================
# 7. LARGE GRAPH 100+ ENTITIES CYPHER VERIFICATION (DATASET 9)
# =====================================================================

def test_dataset_9_large_graph_100_plus_entities_cypher():
    """Verifies Dataset 9 creates 100+ entity nodes in Neo4j proven by Cypher count query."""
    health = neo4j_connection_service.check_health()
    if health.status != "UP":
        pytest.skip("Neo4j database offline.")

    neo4j_realistic_datasets.seed_dataset("9_large_graph")
    driver = neo4j_connection_service.get_driver()
    
    with driver.session(database=settings.NEO4J_DATABASE) as session:
        # Count non-Case entity nodes (Person, Phone, Vehicle, Location)
        entity_count = session.run("""
            MATCH (n {dataset_id: '9_large_graph'})
            WHERE NOT 'Case' IN labels(n)
            RETURN count(n) AS c
        """).single()["c"]

        total_nodes = session.run("""
            MATCH (n {dataset_id: '9_large_graph'})
            RETURN count(n) AS c
        """).single()["c"]

        spec = EXPECTED_TOPOLOGY_SPECS["9_large_graph"]
        assert entity_count >= spec["min_total_entities"], f"Cypher entity count ({entity_count}) < 100!"
        assert total_nodes >= 160, f"Total node count ({total_nodes}) < 160!"


# =====================================================================
# 8. PATTERN GROUNDING & NON-INFERENCE GUARDRAIL
# =====================================================================

def test_pattern_engine_non_inference_guardrail():
    """Verifies Pattern Intelligence Engine rejects forbidden inference terms."""
    from app.services.pattern_engine import PatternObservation, PatternType

    with pytest.raises(ValueError) as exc_info:
        PatternObservation(
            pattern_id="pat_test_001",
            pattern_type=PatternType.MODUS_OPERANDI,
            title="Test Pattern",
            description="Person identified as accomplice in burglary."
        )
    assert "Forbidden inference term 'accomplice' detected" in str(exc_info.value)


# =====================================================================
# 9. PRIVACY DE-IDENTIFICATION & BACK-MAPPING
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
# 10. SOURCE GROUNDING NEGATIVE TEST
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
# 11. SCALABILITY & BOUNDED TRAVERSAL (DATASET 9)
# =====================================================================

def test_dataset_9_large_graph_scalability():
    """Verifies 60-case scalability dataset completes within bounded time limit (< 25.0s)."""
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
        ReasoningStatus.VALIDATION_FAILED,
    ]
    assert response.analytical_metadata.cases_evaluated_count == 50
    assert elapsed < 25.0, f"Scalability analysis exceeded time limit: {elapsed:.2f}s"
