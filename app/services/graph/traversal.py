import logging
import uuid
from typing import Any, Dict, List, Optional, Set
from pydantic import BaseModel, Field, field_validator
from app.services.graph.connection import (
    Neo4jConnectionService,
    _sanitize_error_message,
    neo4j_connection_service,
)

logger = logging.getLogger(__name__)

ALLOWED_NODE_TYPES: Set[str] = {
    "Case",
    "Person",
    "Vehicle",
    "Phone",
    "Location",
    "Evidence",
    "LegalSection",
}

ALLOWED_RELATIONSHIP_TYPES: Set[str] = {
    "HAS_PERSON",
    "HAS_VEHICLE",
    "HAS_PHONE",
    "HAS_LOCATION",
    "HAS_EVIDENCE",
    "HAS_LEGAL_SECTION",
    "RELATED_TO",
}

SENSITIVE_FIELD_NAMES: Set[str] = {
    "date_of_birth",
    "address",
    "password",
    "token",
    "secret",
    "credential",
    "binary",
}


# =====================================================================
# 1. TRAVERSAL CONTRACTS
# =====================================================================

class GraphTraversalRequest(BaseModel):
    """Request contract for controlled multi-hop graph traversal."""

    start_node_id: str
    start_node_type: str = "Case"
    target_node_id: Optional[str] = None
    maximum_depth: int = Field(default=3, ge=1, le=5)
    allowed_node_types: List[str] = Field(default_factory=lambda: sorted(list(ALLOWED_NODE_TYPES)))
    allowed_relationship_types: List[str] = Field(default_factory=lambda: sorted(list(ALLOWED_RELATIONSHIP_TYPES)))
    minimum_relationship_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    include_relationship_metadata: bool = True
    traversal_method: str = "graph-traversal-v1"

    @field_validator("start_node_id", "target_node_id")
    def validate_uuid_field(cls, v: Optional[str]) -> Optional[str]:
        if v is not None:
            uuid.UUID(str(v))
            return str(v)
        return v

    @field_validator("start_node_type")
    def validate_start_node_type(cls, v: str) -> str:
        if v not in ALLOWED_NODE_TYPES:
            raise ValueError(
                f"Unsupported start node type: '{v}'. Must be one of {sorted(list(ALLOWED_NODE_TYPES))}"
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


class GraphPathNode(BaseModel):
    """Node contract in a discovered graph path."""

    node_id: str
    label: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphPathEdge(BaseModel):
    """Edge contract in a discovered graph path."""

    type: str
    source_node_id: str
    target_node_id: str
    properties: Dict[str, Any] = Field(default_factory=dict)


class GraphTraversalPath(BaseModel):
    """Complete structural path model in graph traversal."""

    path_key: str
    hop_count: int
    start_node_id: str
    end_node_id: str
    nodes: List[GraphPathNode]
    edges: List[GraphPathEdge]


class GraphTraversalResult(BaseModel):
    """Top-level result container for graph traversal queries."""

    start_node_id: str
    start_node_type: str
    total_paths: int
    maximum_depth_searched: int
    paths: List[GraphTraversalPath]
    traversal_method: str = "graph-traversal-v1"


# =====================================================================
# 2. TRAVERSAL SERVICE
# =====================================================================

class Neo4jGraphTraversalService:
    """Read-only multi-hop graph intelligence and traversal engine."""

    def __init__(self, connection_service: Neo4jConnectionService = neo4j_connection_service):
        self.connection_service = connection_service

    def traverse(self, request: GraphTraversalRequest) -> GraphTraversalResult:
        """Executes a bounded, read-only multi-hop Cypher traversal returning structural paths."""
        try:
            driver = self.connection_service.get_driver()
            with driver.session(database=self.connection_service.database) as session:
                # 1. Verify start node exists
                start_check = session.run(
                    "MATCH (n {node_id: $start_id}) WHERE $start_label IN labels(n) RETURN count(n) AS c",
                    {"start_id": request.start_node_id, "start_label": request.start_node_type},
                ).single()

                if not start_check or start_check["c"] == 0:
                    logger.info("Start node %s (%s) not found in graph.", request.start_node_id, request.start_node_type)
                    return GraphTraversalResult(
                        start_node_id=request.start_node_id,
                        start_node_type=request.start_node_type,
                        total_paths=0,
                        maximum_depth_searched=request.maximum_depth,
                        paths=[],
                        traversal_method=request.traversal_method,
                    )

                # 2. Build Cypher MATCH query dynamically using type-safe parameters and allowlisted relationship types
                depth = max(1, min(5, request.maximum_depth))
                
                # Format allowlisted relationship types for variable length pattern in Neo4j 5 syntax: [:REL1|REL2*1..depth]
                rel_types_str = ":" + "|".join(request.allowed_relationship_types)
                
                cypher_query = f"""
                MATCH (start {{node_id: $start_id}})
                WHERE $start_label IN labels(start)
                MATCH path = (start)-[{rel_types_str}*1..{depth}]-(target)
                WHERE ALL(n IN nodes(path) WHERE any(lbl IN labels(n) WHERE lbl IN $allowed_node_types))
                """

                params: Dict[str, Any] = {
                    "start_id": request.start_node_id,
                    "start_label": request.start_node_type,
                    "allowed_node_types": request.allowed_node_types,
                }

                if request.target_node_id:
                    cypher_query += " AND target.node_id = $target_id"
                    params["target_id"] = request.target_node_id

                if request.minimum_relationship_confidence is not None:
                    cypher_query += """
                    AND ALL(r IN relationships(path) WHERE type(r) <> 'RELATED_TO' OR r.confidence_score >= $min_conf)
                    """
                    params["min_conf"] = request.minimum_relationship_confidence

                cypher_query += " RETURN path"

                # 3. Run Query & Process Record Objects
                result = session.run(cypher_query, params)
                path_map: Dict[str, GraphTraversalPath] = {}

                for record in result:
                    neo4j_path = record["path"]
                    parsed_path = self._parse_neo4j_path(neo4j_path, request.include_relationship_metadata)
                    if parsed_path and parsed_path.path_key not in path_map:
                        path_map[parsed_path.path_key] = parsed_path

                # 4. Deterministic sorting: 1. hop_count, 2. end_node_id, 3. path_key
                sorted_paths = sorted(
                    list(path_map.values()),
                    key=lambda p: (p.hop_count, p.end_node_id, p.path_key),
                )

                return GraphTraversalResult(
                    start_node_id=request.start_node_id,
                    start_node_type=request.start_node_type,
                    total_paths=len(sorted_paths),
                    maximum_depth_searched=depth,
                    paths=sorted_paths,
                    traversal_method=request.traversal_method,
                )

        except Exception as e:
            sanitized_msg = _sanitize_error_message(e, self.connection_service.password)
            logger.error("Failed executing graph traversal query: %s", sanitized_msg)
            raise RuntimeError(f"Graph traversal failed: {sanitized_msg}") from None

    # =====================================================================
    # PRIVATE PATH PARSING HELPER
    # =====================================================================

    def _parse_neo4j_path(self, neo4j_path: Any, include_metadata: bool) -> Optional[GraphTraversalPath]:
        """Parses a Neo4j driver Path object into a GraphTraversalPath contract."""
        nodes_list: List[GraphPathNode] = []
        edges_list: List[GraphPathEdge] = []

        # Parse nodes
        for node in neo4j_path.nodes:
            lbl = list(node.labels)[0] if node.labels else "Unknown"
            props = {k: v for k, v in dict(node).items() if k not in SENSITIVE_FIELD_NAMES}
            node_id = props.get("node_id", str(node.element_id if hasattr(node, "element_id") else node.id))
            nodes_list.append(GraphPathNode(node_id=node_id, label=lbl, properties=props))

        # Parse relationships
        for rel in neo4j_path.relationships:
            rel_type = rel.type
            src_node = rel.start_node
            tgt_node = rel.end_node
            src_id = str(src_node.get("node_id", src_node.element_id if hasattr(src_node, "element_id") else src_node.id))
            tgt_id = str(tgt_node.get("node_id", tgt_node.element_id if hasattr(tgt_node, "element_id") else tgt_node.id))

            props = {k: v for k, v in dict(rel).items() if k not in SENSITIVE_FIELD_NAMES} if include_metadata else {}

            edges_list.append(
                GraphPathEdge(
                    type=rel_type,
                    source_node_id=src_id,
                    target_node_id=tgt_id,
                    properties=props,
                )
            )

        if not nodes_list:
            return None

        start_id = nodes_list[0].node_id
        end_id = nodes_list[-1].node_id
        hop_count = len(edges_list)

        # Build unique canonical path key
        path_segments = []
        for i in range(len(edges_list)):
            n_curr = nodes_list[i]
            edge = edges_list[i]
            n_next = nodes_list[i + 1]
            path_segments.append(f"({n_curr.label}:{n_curr.node_id})-[{edge.type}]->({n_next.label}:{n_next.node_id})")

        path_key = "->".join(path_segments)

        return GraphTraversalPath(
            path_key=path_key,
            hop_count=hop_count,
            start_node_id=start_id,
            end_node_id=end_id,
            nodes=nodes_list,
            edges=edges_list,
        )


neo4j_graph_traversal_service = Neo4jGraphTraversalService()
