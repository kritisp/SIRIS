import logging
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, Field, field_validator
from app.services.graph.connection import (
    Neo4jConnectionService,
    _sanitize_error_message,
    neo4j_connection_service,
)
from app.services.graph.traversal import (
    ALLOWED_NODE_TYPES,
    ALLOWED_RELATIONSHIP_TYPES,
    SENSITIVE_FIELD_NAMES,
)

logger = logging.getLogger(__name__)


# =====================================================================
# 1. COMMUNITY DETECTION CONTRACTS
# =====================================================================

class CommunityDetectionRequest(BaseModel):
    """Request contract for community detection and dense subgraph clustering."""

    target_node_id: Optional[str] = None
    target_node_type: Optional[str] = None
    maximum_depth: int = Field(default=3, ge=1, le=5)
    minimum_community_size: int = Field(default=2, ge=2)
    minimum_density: float = Field(default=0.0, ge=0.0, le=1.0)
    allowed_node_types: List[str] = Field(default_factory=lambda: sorted(list(ALLOWED_NODE_TYPES)))
    allowed_relationship_types: List[str] = Field(default_factory=lambda: sorted(list(ALLOWED_RELATIONSHIP_TYPES)))
    minimum_relationship_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    include_edge_summary: bool = True
    detection_method: str = "density-clustering-v1"
    methodology_version: str = "community-detection-v1"

    @field_validator("target_node_id")
    def validate_target_node_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            uuid.UUID(str(v))
            return str(v)
        return v

    @field_validator("target_node_type")
    def validate_target_node_type(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in ALLOWED_NODE_TYPES:
            raise ValueError(
                f"Unsupported node type: '{v}'. Must be one of {sorted(list(ALLOWED_NODE_TYPES))}"
            )
        return v

    @field_validator("allowed_node_types")
    def validate_allowed_node_types(cls, v: List[str]) -> List[str]:
        invalid = [t for t in v if t not in ALLOWED_NODE_TYPES]
        if invalid:
            raise ValueError(
                f"Unsupported node type(s): {invalid}. Allowed node types are {sorted(list(ALLOWED_NODE_TYPES))}"
            )
        return v

    @field_validator("allowed_relationship_types")
    def validate_allowed_rel_types(cls, v: List[str]) -> List[str]:
        invalid = [r for r in v if r not in ALLOWED_RELATIONSHIP_TYPES]
        if invalid:
            raise ValueError(
                f"Unsupported relationship type(s): {invalid}. Allowed relationship types are {sorted(list(ALLOWED_RELATIONSHIP_TYPES))}"
            )
        return v


class CommunityMember(BaseModel):
    """Member node in a discovered community cluster."""

    node_id: str
    node_type: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)
    degree: int = 0


class CommunityEdgeSummary(BaseModel):
    """Internal edge summary in a community cluster."""

    source_node_id: str
    target_node_id: str
    relationship_type: str
    weight: float = 1.0


class CommunityCluster(BaseModel):
    """Discovered community cluster / dense subgraph payload."""

    community_id: str
    member_count: int
    density: float
    internal_edge_count: int
    case_count: int
    station_count: int
    spans_cross_station: bool
    node_type_distribution: Dict[str, int] = Field(default_factory=dict)
    relationship_type_distribution: Dict[str, int] = Field(default_factory=dict)
    members: List[CommunityMember] = Field(default_factory=list)
    edges: List[CommunityEdgeSummary] = Field(default_factory=list)


class CommunityDetectionResult(BaseModel):
    """Top-level container for community detection analytical results."""

    target_node_id: Optional[str] = None
    total_nodes_evaluated: int
    total_communities_detected: int
    communities: List[CommunityCluster]
    detection_method: str = "density-clustering-v1"
    methodology_version: str = "community-detection-v1"


# =====================================================================
# 2. COMMUNITY DETECTION SERVICE
# =====================================================================

class Neo4jCommunityDetectionService:
    """Read-only community detection and dense subgraph clustering engine."""

    def __init__(self, connection_service: Neo4jConnectionService = neo4j_connection_service):
        self.connection_service = connection_service

    def detect_communities(self, request: CommunityDetectionRequest) -> CommunityDetectionResult:
        """Executes read-only Cypher queries to evaluate graph components, compute density, and cluster communities."""
        try:
            driver = self.connection_service.get_driver()
            with driver.session(database=self.connection_service.database) as session:
                # 1. Fetch relevant graph nodes
                nodes_query = "MATCH (n) WHERE head(labels(n)) IN $allowed_types RETURN n.node_id AS node_id, head(labels(n)) AS label, properties(n) AS props"
                params: Dict[str, Any] = {"allowed_types": request.allowed_node_types}

                if request.target_node_id:
                    depth = max(1, min(5, request.maximum_depth))
                    rel_types_str = ":" + "|".join(request.allowed_relationship_types)
                    nodes_query = f"""
                    MATCH (start {{node_id: $target_id}})
                    MATCH path = (start)-[{rel_types_str}*0..{depth}]-(n)
                    WHERE ALL(m IN nodes(path) WHERE head(labels(m)) IN $allowed_types)
                    RETURN DISTINCT n.node_id AS node_id, head(labels(n)) AS label, properties(n) AS props
                    """
                    params["target_id"] = request.target_node_id

                nodes_result = session.run(nodes_query, params)
                nodes_data = [dict(record) for record in nodes_result]

                if not nodes_data:
                    return CommunityDetectionResult(
                        target_node_id=request.target_node_id,
                        total_nodes_evaluated=0,
                        total_communities_detected=0,
                        communities=[],
                        detection_method=request.detection_method,
                        methodology_version=request.methodology_version,
                    )

                node_id_set = {n["node_id"] for n in nodes_data if n.get("node_id")}

                # 2. Fetch edges between node set
                edges_query = """
                MATCH (a)-[r]->(b)
                WHERE a.node_id IN $ids AND b.node_id IN $ids AND type(r) IN $allowed_rels
                """
                if request.minimum_relationship_confidence is not None:
                    edges_query += " AND (type(r) <> 'RELATED_TO' OR r.confidence_score >= $min_conf)"
                    params["min_conf"] = request.minimum_relationship_confidence

                edges_query += " RETURN a.node_id AS src, b.node_id AS tgt, type(r) AS rel_type, properties(r) AS props"
                params["allowed_rels"] = request.allowed_relationship_types
                params["ids"] = list(node_id_set)

                edges_result = session.run(edges_query, params)
                edges_data = [dict(record) for record in edges_result]

                # 3. Build Adjacency & Edge maps
                adj: Dict[str, Set[str]] = {nid: set() for nid in node_id_set}
                node_degrees: Dict[str, int] = {nid: 0 for nid in node_id_set}
                node_labels: Dict[str, str] = {n["node_id"]: n["label"] for n in nodes_data if n.get("node_id")}
                node_props: Dict[str, dict] = {n["node_id"]: n["props"] for n in nodes_data if n.get("node_id")}

                unique_structural_pairs: Dict[Tuple[str, str], List[dict]] = {}

                for edge in edges_data:
                    src = edge["src"]
                    tgt = edge["tgt"]
                    rel_type = edge["rel_type"]
                    props = edge["props"] or {}

                    adj[src].add(tgt)
                    adj[tgt].add(src)
                    node_degrees[src] += 1
                    node_degrees[tgt] += 1

                    pair_key = tuple(sorted([src, tgt]))
                    if pair_key not in unique_structural_pairs:
                        unique_structural_pairs[pair_key] = []
                    unique_structural_pairs[pair_key].append({"src": src, "tgt": tgt, "type": rel_type, "props": props})

                # 4. Discover connected clusters via BFS
                visited: Set[str] = set()
                candidate_clusters: List[CommunityCluster] = []

                for nid in sorted(list(node_id_set)):
                    if nid not in visited:
                        comp_nodes: Set[str] = set()
                        queue = [nid]
                        visited.add(nid)

                        while queue:
                            curr = queue.pop(0)
                            comp_nodes.add(curr)
                            for nxt in adj[curr]:
                                if nxt not in visited:
                                    visited.add(nxt)
                                    queue.append(nxt)

                        sorted_comp_nodes = sorted(list(comp_nodes))
                        N = len(sorted_comp_nodes)

                        # Count unique structural undirected edges internal to cluster
                        comp_pair_keys = [
                            pk for pk in unique_structural_pairs
                            if pk[0] in comp_nodes and pk[1] in comp_nodes
                        ]
                        E_undirected = len(comp_pair_keys)

                        # Undirected Graph Density: 2E / (N * (N - 1))
                        density = (2.0 * float(E_undirected)) / float(N * (N - 1)) if N >= 2 else 0.0
                        density = min(1.0, max(0.0, round(density, 4)))

                        # Filter by minimum size and density
                        if N < request.minimum_community_size or density < request.minimum_density:
                            continue

                        # Deterministic Community ID: community:<min_node_id>
                        comp_id = f"community:{sorted_comp_nodes[0]}"

                        # Node type & Relationship type distributions
                        node_type_dist: Dict[str, int] = {}
                        members_list: List[CommunityMember] = []
                        cases_in_comp = []

                        for cn in sorted_comp_nodes:
                            lbl = node_labels.get(cn, "Unknown")
                            node_type_dist[lbl] = node_type_dist.get(lbl, 0) + 1

                            if lbl == "Case":
                                cases_in_comp.append(cn)

                            clean_props = {k: v for k, v in node_props.get(cn, {}).items() if k not in SENSITIVE_FIELD_NAMES}
                            members_list.append(
                                CommunityMember(
                                    node_id=cn,
                                    node_type=lbl,
                                    label=lbl,
                                    properties=clean_props,
                                    degree=node_degrees.get(cn, 0),
                                )
                            )

                        # Sort members deterministically: (node_type, node_id)
                        members_list.sort(key=lambda m: (m.node_type, m.node_id))

                        # Relationship distribution & edge summary
                        rel_type_dist: Dict[str, int] = {}
                        edge_summary_list: List[CommunityEdgeSummary] = []
                        total_internal_edges = 0

                        for pk in sorted(comp_pair_keys):
                            rel_list = unique_structural_pairs[pk]
                            for r_info in rel_list:
                                total_internal_edges += 1
                                r_type = r_info["type"]
                                rel_type_dist[r_type] = rel_type_dist.get(r_type, 0) + 1
                                w = float(r_info["props"].get("confidence_score", 1.0)) if r_type == "RELATED_TO" else 1.0

                                if request.include_edge_summary:
                                    edge_summary_list.append(
                                        CommunityEdgeSummary(
                                            source_node_id=r_info["src"],
                                            target_node_id=r_info["tgt"],
                                            relationship_type=r_type,
                                            weight=w,
                                        )
                                    )

                        # Sort edge summaries deterministically
                        edge_summary_list.sort(key=lambda e: (e.source_node_id, e.target_node_id, e.relationship_type))

                        # Station statistics
                        stations = {node_props[c].get("station_id") for c in cases_in_comp if node_props[c].get("station_id")}

                        candidate_clusters.append(
                            CommunityCluster(
                                community_id=comp_id,
                                member_count=N,
                                density=density,
                                internal_edge_count=total_internal_edges,
                                case_count=len(cases_in_comp),
                                station_count=len(stations),
                                spans_cross_station=len(stations) > 1,
                                node_type_distribution=dict(sorted(node_type_dist.items())),
                                relationship_type_distribution=dict(sorted(rel_type_dist.items())),
                                members=members_list,
                                edges=edge_summary_list,
                            )
                        )

                # Deterministic sorting for community clusters: 1. member_count desc, 2. density desc, 3. community_id asc
                candidate_clusters.sort(key=lambda c: (-c.member_count, -c.density, c.community_id))

                return CommunityDetectionResult(
                    target_node_id=request.target_node_id,
                    total_nodes_evaluated=len(node_id_set),
                    total_communities_detected=len(candidate_clusters),
                    communities=candidate_clusters,
                    detection_method=request.detection_method,
                    methodology_version=request.methodology_version,
                )

        except Exception as e:
            sanitized_msg = _sanitize_error_message(e, self.connection_service.password)
            logger.error("Failed executing community detection: %s", sanitized_msg)
            raise RuntimeError(f"Community detection execution failed: {sanitized_msg}") from None


neo4j_community_detection_service = Neo4jCommunityDetectionService()
