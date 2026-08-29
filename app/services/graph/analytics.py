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
# 1. NETWORK ANALYTICS CONTRACTS
# =====================================================================

class NetworkAnalyticsRequest(BaseModel):
    """Request contract for network analytics calculations."""

    target_node_id: Optional[str] = None
    target_node_type: Optional[str] = None
    include_components: bool = True
    include_connectors: bool = True
    max_subgraph_depth: int = Field(default=3, ge=1, le=5)
    analytics_method: str = "network-analytics-v1"

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


class NodeCentralityMetric(BaseModel):
    """Centrality metrics container for a node."""

    degree_centrality: float = Field(ge=0.0, le=1.0)
    betweenness_centrality: float = Field(ge=0.0, le=1.0)
    closeness_centrality: float = Field(ge=0.0, le=1.0)


class NetworkNodeMetrics(BaseModel):
    """Network-level analytics metrics for an individual graph node."""

    node_id: str
    node_type: str
    label: str
    total_degree: int
    incoming_degree: int
    outgoing_degree: int
    weighted_degree: float
    connected_station_count: int
    connected_case_count: int
    centrality: NodeCentralityMetric
    component_id: str
    is_connector_node: bool = False
    connector_role_summary: Optional[str] = None


class NetworkComponentSummary(BaseModel):
    """Summary metrics for a connected component in the analytical graph."""

    component_id: str
    component_size: int
    case_count: int
    station_count: int
    spans_cross_station: bool
    nodes: List[str] = Field(default_factory=list)


class NetworkAnalyticsResult(BaseModel):
    """Top-level analytical result payload for network analytics."""

    target_node_id: Optional[str] = None
    total_nodes_analyzed: int
    total_components: int
    node_metrics: List[NetworkNodeMetrics]
    components: List[NetworkComponentSummary]
    analytics_method: str = "network-analytics-v1"
    methodology_version: str = "network-analytics-v1"


# =====================================================================
# 2. NETWORK ANALYTICS SERVICE
# =====================================================================

class Neo4jNetworkAnalyticsService:
    """Read-only network analytics engine calculating degree, centrality, connected components, and bridge metrics."""

    def __init__(self, connection_service: Neo4jConnectionService = neo4j_connection_service):
        self.connection_service = connection_service

    def analyze_network(self, request: NetworkAnalyticsRequest) -> NetworkAnalyticsResult:
        """Executes read-only graph analytics queries and returns deterministic network metrics."""
        try:
            driver = self.connection_service.get_driver()
            with driver.session(database=self.connection_service.database) as session:
                # 1. Fetch relevant graph nodes and edges
                nodes_query = "MATCH (n) RETURN n.node_id AS node_id, head(labels(n)) AS label, properties(n) AS props"
                if request.target_node_id:
                    # Bounded subgraph around target node
                    depth = request.max_subgraph_depth
                    nodes_query = f"""
                    MATCH (start {{node_id: $target_id}})
                    MATCH path = (start)-[*0..{depth}]-(n)
                    RETURN DISTINCT n.node_id AS node_id, head(labels(n)) AS label, properties(n) AS props
                    """

                params = {"target_id": request.target_node_id} if request.target_node_id else {}
                nodes_result = session.run(nodes_query, params)
                nodes_data = [dict(record) for record in nodes_result]

                if not nodes_data:
                    return NetworkAnalyticsResult(
                        target_node_id=request.target_node_id,
                        total_nodes_analyzed=0,
                        total_components=0,
                        node_metrics=[],
                        components=[],
                        analytics_method=request.analytics_method,
                    )

                node_id_set = {n["node_id"] for n in nodes_data if n.get("node_id")}

                # 2. Fetch edges between these nodes
                edges_query = """
                MATCH (a)-[r]->(b)
                WHERE a.node_id IN $ids AND b.node_id IN $ids
                RETURN a.node_id AS src, b.node_id AS tgt, type(r) AS rel_type, properties(r) AS props
                """
                edges_result = session.run(edges_query, {"ids": list(node_id_set)})
                edges_data = [dict(record) for record in edges_result]

                # 3. Build Adjacency Structures for Analytics
                adj: Dict[str, Set[str]] = {nid: set() for nid in node_id_set}
                inc_degree: Dict[str, int] = {nid: 0 for nid in node_id_set}
                out_degree: Dict[str, int] = {nid: 0 for nid in node_id_set}
                weighted_degree: Dict[str, float] = {nid: 0.0 for nid in node_id_set}

                node_labels: Dict[str, str] = {n["node_id"]: n["label"] for n in nodes_data if n.get("node_id")}
                node_props: Dict[str, dict] = {n["node_id"]: n["props"] for n in nodes_data if n.get("node_id")}

                for edge in edges_data:
                    src = edge["src"]
                    tgt = edge["tgt"]
                    rel_type = edge["rel_type"]
                    props = edge["props"] or {}

                    adj[src].add(tgt)
                    adj[tgt].add(src)

                    out_degree[src] += 1
                    inc_degree[tgt] += 1

                    # Weight calculation: RELATED_TO uses confidence_score, others 1.0
                    weight = float(props.get("confidence_score", 1.0)) if rel_type == "RELATED_TO" else 1.0
                    weighted_degree[src] += weight
                    weighted_degree[tgt] += weight

                # 4. Connected Component Analysis (BFS)
                visited: Set[str] = set()
                components_list: List[NetworkComponentSummary] = []
                node_component_map: Dict[str, str] = {}

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
                        comp_id = f"comp:{sorted_comp_nodes[0]}"

                        for cn in sorted_comp_nodes:
                            node_component_map[cn] = comp_id

                        # Component statistics
                        cases = [cn for cn in sorted_comp_nodes if node_labels.get(cn) == "Case"]
                        stations = {node_props[c].get("station_id") for c in cases if node_props[c].get("station_id")}

                        components_list.append(
                            NetworkComponentSummary(
                                component_id=comp_id,
                                component_size=len(sorted_comp_nodes),
                                case_count=len(cases),
                                station_count=len(stations),
                                spans_cross_station=len(stations) > 1,
                                nodes=sorted_comp_nodes,
                            )
                        )

                # Sort components deterministically: 1. component_size desc, 2. component_id asc
                components_list.sort(key=lambda c: (-c.component_size, c.component_id))

                # 5. Compute Centrality Metrics per Component
                node_centrality: Dict[str, NodeCentralityMetric] = {}
                connected_stations_map: Dict[str, int] = {}
                connected_cases_map: Dict[str, int] = {}

                for comp in components_list:
                    c_nodes = comp.nodes
                    N = len(c_nodes)

                    # Compute connected cases & stations per node in component
                    for nid in c_nodes:
                        reachable_cases = [
                            c for c in c_nodes if node_labels.get(c) == "Case" and (c in adj[nid] or c == nid)
                        ]
                        stns = {node_props[c].get("station_id") for c in reachable_cases if node_props[c].get("station_id")}
                        connected_cases_map[nid] = len(reachable_cases)
                        connected_stations_map[nid] = len(stns)

                    for nid in c_nodes:
                        # Degree Centrality: degree / (N - 1)
                        tot_deg = out_degree[nid] + inc_degree[nid]
                        deg_cent = float(tot_deg) / float(N - 1) if N > 1 else 0.0
                        deg_cent = min(1.0, max(0.0, deg_cent))

                        # Closeness Centrality: (N - 1) / sum(shortest_path_distances)
                        closeness_cent = self._compute_closeness_centrality(nid, c_nodes, adj)

                        # Betweenness Centrality: shortest path fraction passing through node
                        between_cent = self._compute_betweenness_centrality(nid, c_nodes, adj)

                        node_centrality[nid] = NodeCentralityMetric(
                            degree_centrality=round(deg_cent, 4),
                            betweenness_centrality=round(between_cent, 4),
                            closeness_centrality=round(closeness_cent, 4),
                        )

                # 6. Assemble Node Metrics & Connector Analysis
                node_metrics_list: List[NetworkNodeMetrics] = []

                for nid in sorted(list(node_id_set)):
                    lbl = node_labels.get(nid, "Unknown")
                    cent = node_centrality[nid]
                    tot_deg = out_degree[nid] + inc_degree[nid]
                    c_stns = connected_stations_map.get(nid, 0)
                    c_cases = connected_cases_map.get(nid, 0)

                    is_connector = False
                    connector_summary = None

                    # Connector / Bridge criteria: high betweenness OR bridging multiple stations/cases
                    if cent.betweenness_centrality >= 0.2:
                        is_connector = True
                        connector_summary = "High betweenness centrality connector node in network component."
                    elif c_stns >= 2:
                        is_connector = True
                        connector_summary = "Cross-station network connector linking multiple police stations."
                    elif lbl != "Case" and c_cases >= 2:
                        is_connector = True
                        connector_summary = f"Shared {lbl.lower()} entity bridging {c_cases} distinct cases."

                    node_metrics_list.append(
                        NetworkNodeMetrics(
                            node_id=nid,
                            node_type=lbl,
                            label=lbl,
                            total_degree=tot_deg,
                            incoming_degree=inc_degree[nid],
                            outgoing_degree=out_degree[nid],
                            weighted_degree=round(weighted_degree[nid], 4),
                            connected_station_count=c_stns,
                            connected_case_count=c_cases,
                            centrality=cent,
                            component_id=node_component_map[nid],
                            is_connector_node=is_connector,
                            connector_role_summary=connector_summary,
                        )
                    )

                # Sort node metrics deterministically: (node_type, node_id)
                node_metrics_list.sort(key=lambda nm: (nm.node_type, nm.node_id))

                return NetworkAnalyticsResult(
                    target_node_id=request.target_node_id,
                    total_nodes_analyzed=len(node_id_set),
                    total_components=len(components_list),
                    node_metrics=node_metrics_list,
                    components=components_list,
                    analytics_method=request.analytics_method,
                )

        except Exception as e:
            sanitized_msg = _sanitize_error_message(e, self.connection_service.password)
            logger.error("Failed executing network analytics: %s", sanitized_msg)
            raise RuntimeError(f"Network analytics execution failed: {sanitized_msg}") from None

    # =====================================================================
    # PRIVATE CENTRALITY COMPUTATION HELPERS
    # =====================================================================

    def _compute_closeness_centrality(
        self, target_id: str, comp_nodes: List[str], adj: Dict[str, Set[str]]
    ) -> float:
        """Computes closeness centrality for target_id within its connected component."""
        N = len(comp_nodes)
        if N <= 1:
            return 0.0

        # Shortest path distances via BFS
        dist: Dict[str, int] = {target_id: 0}
        queue = [target_id]

        while queue:
            curr = queue.pop(0)
            curr_d = dist[curr]
            for nxt in adj[curr]:
                if nxt in comp_nodes and nxt not in dist:
                    dist[nxt] = curr_d + 1
                    queue.append(nxt)

        total_distance = sum(dist.values())
        if total_distance == 0:
            return 0.0

        closeness = float(N - 1) / float(total_distance)
        return min(1.0, max(0.0, closeness))

    def _compute_betweenness_centrality(
        self, target_id: str, comp_nodes: List[str], adj: Dict[str, Set[str]]
    ) -> float:
        """Computes normalized betweenness centrality for target_id within its component."""
        N = len(comp_nodes)
        if N <= 2:
            return 0.0

        betweenness_sum = 0.0

        # Iterate over all node pairs (s, t) where s != t != target_id
        for i in range(len(comp_nodes)):
            s = comp_nodes[i]
            if s == target_id:
                continue
            for j in range(i + 1, len(comp_nodes)):
                t = comp_nodes[j]
                if t == target_id:
                    continue

                # Find all shortest paths between s and t
                paths = self._all_shortest_paths(s, t, comp_nodes, adj)
                if not paths:
                    continue

                total_sp = len(paths)
                sp_through_v = sum(1 for p in paths if target_id in p)
                betweenness_sum += float(sp_through_v) / float(total_sp)

        # Normalize by maximum possible pairs in undirected graph: (N - 1)(N - 2) / 2
        norm_factor = (float(N - 1) * float(N - 2)) / 2.0
        if norm_factor == 0.0:
            return 0.0

        norm_betweenness = betweenness_sum / norm_factor
        return min(1.0, max(0.0, norm_betweenness))

    def _all_shortest_paths(
        self, s: str, t: str, comp_nodes: List[str], adj: Dict[str, Set[str]]
    ) -> List[List[str]]:
        """BFS helper returning all shortest paths between node s and node t."""
        if s == t:
            return [[s]]

        queue = [[s]]
        shortest_paths: List[List[str]] = []
        min_len = None

        while queue:
            path = queue.pop(0)
            curr = path[-1]

            if min_len is not None and len(path) > min_len:
                break

            if curr == t:
                if min_len is None:
                    min_len = len(path)
                shortest_paths.append(path)
                continue

            for nxt in adj[curr]:
                if nxt in comp_nodes and nxt not in path:
                    queue.append(path + [nxt])

        return shortest_paths


neo4j_network_analytics_service = Neo4jNetworkAnalyticsService()
