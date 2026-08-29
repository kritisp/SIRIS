import hashlib
import logging
import uuid
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.case import Case
from app.services.graph.analytics import NetworkAnalyticsResult
from app.services.graph.community import CommunityDetectionResult
from app.services.graph.traversal import GraphTraversalResult
from app.services.relationship_engine import RelationshipConfidenceAssessment

logger = logging.getLogger(__name__)

PATTERN_INTELLIGENCE_METHODOLOGY_VERSION = "pattern-intelligence-v1"

# Explicit forbidden inference terms safeguard
FORBIDDEN_INFERENCE_TERMS: Set[str] = {
    "criminal network",
    "mastermind",
    "accomplice",
    "gang",
    "conspiracy",
    "offender",
    "culprit",
    "guilty",
    "perpetrator",
}


# =====================================================================
# 1. PATTERN TAXONOMY & CONTRACTS
# =====================================================================

class PatternType(str, Enum):
    """Supported pattern categories taxonomy."""

    MODUS_OPERANDI = "MODUS_OPERANDI"
    RECURRING_ENTITY = "RECURRING_ENTITY"
    RECURRING_LOCATION = "RECURRING_LOCATION"
    RECURRING_VEHICLE_PHONE = "RECURRING_VEHICLE_PHONE"
    TEMPORAL_CLUSTER = "TEMPORAL_CLUSTER"
    GEOGRAPHIC_CROSS_STATION = "GEOGRAPHIC_CROSS_STATION"
    CASE_CHARACTERISTIC = "CASE_CHARACTERISTIC"
    GRAPH_STRUCTURAL = "GRAPH_STRUCTURAL"


class PatternObservation(BaseModel):
    """Structured, evidence-backed pattern observation payload."""

    pattern_id: str
    pattern_type: PatternType
    title: str
    description: str
    case_ids: List[str] = Field(default_factory=list)
    entity_ids: List[str] = Field(default_factory=list)
    entity_types: List[str] = Field(default_factory=list)
    station_ids: List[str] = Field(default_factory=list)
    supporting_signals: List[str] = Field(default_factory=list)
    occurrence_count: int
    structural_strength: float = Field(ge=0.0, le=1.0)
    provenance: Dict[str, Any] = Field(default_factory=dict)
    methodology_version: str = PATTERN_INTELLIGENCE_METHODOLOGY_VERSION

    @field_validator("title", "description")
    def validate_non_inference_language(cls, v: str) -> str:
        lower_v = v.lower()
        for term in FORBIDDEN_INFERENCE_TERMS:
            if term in lower_v:
                raise ValueError(
                    f"Forbidden inference term '{term}' detected in pattern output. Pattern Intelligence must remain non-judgmental and observation-based."
                )
        return v


class PatternDetectionRequest(BaseModel):
    """Request contract for Pattern Intelligence calculations."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    cases: List[Case] = Field(default_factory=list)
    minimum_recurrence: int = Field(default=2, ge=2)
    temporal_window_days: Optional[int] = Field(default=30, ge=1)
    minimum_supporting_signals: int = Field(default=1, ge=1)
    allowed_pattern_types: Optional[List[PatternType]] = None
    graph_analytics_result: Optional[NetworkAnalyticsResult] = None
    community_detection_result: Optional[CommunityDetectionResult] = None
    traversal_results: Optional[List[GraphTraversalResult]] = None
    confidence_assessments: Optional[List[RelationshipConfidenceAssessment]] = None
    methodology_version: str = PATTERN_INTELLIGENCE_METHODOLOGY_VERSION


class PatternDetectionResult(BaseModel):
    """Top-level analytical container for detected pattern observations."""

    total_cases_evaluated: int
    total_patterns_detected: int
    pattern_distribution: Dict[str, int] = Field(default_factory=dict)
    patterns: List[PatternObservation] = Field(default_factory=list)
    methodology_version: str = PATTERN_INTELLIGENCE_METHODOLOGY_VERSION


# =====================================================================
# 2. PATTERN INTELLIGENCE ENGINE SERVICE
# =====================================================================

class PatternIntelligenceEngine:
    """Deterministic, read-only Pattern Intelligence Engine detecting structured observations across cases and graph analytics."""

    def detect_patterns(self, request: PatternDetectionRequest) -> PatternDetectionResult:
        """Evaluates input cases, features, assessments, and graph analytical results to detect structured patterns."""
        cases = request.cases
        patterns: List[PatternObservation] = []

        allowed_types = set(request.allowed_pattern_types) if request.allowed_pattern_types else set(PatternType)

        # 1. Modus Operandi Patterns
        if PatternType.MODUS_OPERANDI in allowed_types:
            patterns.extend(self._detect_modus_operandi_patterns(cases, request))

        # 2. Recurring Entity Patterns (Person)
        if PatternType.RECURRING_ENTITY in allowed_types:
            patterns.extend(self._detect_recurring_person_patterns(cases, request))

        # 3. Recurring Location Patterns
        if PatternType.RECURRING_LOCATION in allowed_types:
            patterns.extend(self._detect_recurring_location_patterns(cases, request))

        # 4. Recurring Vehicle & Phone Patterns
        if PatternType.RECURRING_VEHICLE_PHONE in allowed_types:
            patterns.extend(self._detect_recurring_vehicle_phone_patterns(cases, request))

        # 5. Temporal Cluster Patterns
        if PatternType.TEMPORAL_CLUSTER in allowed_types:
            patterns.extend(self._detect_temporal_patterns(cases, request))

        # 6. Geographic / Cross-Station Patterns
        if PatternType.GEOGRAPHIC_CROSS_STATION in allowed_types:
            patterns.extend(self._detect_cross_station_patterns(cases, request))

        # 7. Case Characteristic Combination Patterns
        if PatternType.CASE_CHARACTERISTIC in allowed_types:
            patterns.extend(self._detect_case_characteristic_patterns(cases, request))

        # 8. Graph Structural Patterns (From 5E, 5F, 5G)
        if PatternType.GRAPH_STRUCTURAL in allowed_types:
            patterns.extend(self._detect_graph_structural_patterns(cases, request))

        # Deduplicate & Filter patterns below minimum recurrence or supporting signal threshold
        filtered_patterns = [
            p for p in patterns
            if p.occurrence_count >= request.minimum_recurrence
            and len(p.supporting_signals) >= request.minimum_supporting_signals
        ]

        # Deterministic sorting: 1. occurrence_count desc, 2. structural_strength desc, 3. pattern_type asc, 4. pattern_id asc
        filtered_patterns.sort(
            key=lambda p: (-p.occurrence_count, -p.structural_strength, p.pattern_type.value, p.pattern_id)
        )

        # Compute distribution summary
        dist: Dict[str, int] = {}
        for p in filtered_patterns:
            dist[p.pattern_type.value] = dist.get(p.pattern_type.value, 0) + 1

        return PatternDetectionResult(
            total_cases_evaluated=len(cases),
            total_patterns_detected=len(filtered_patterns),
            pattern_distribution=dict(sorted(dist.items())),
            patterns=filtered_patterns,
            methodology_version=request.methodology_version,
        )

    # =====================================================================
    # PRIVATE PATTERN DETECTION DETECTORS
    # =====================================================================

    def _detect_modus_operandi_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []
        mo_map: Dict[Tuple[str, str], List[Case]] = {}

        for case in cases:
            key = (case.crime_category, case.crime_type)
            if key not in mo_map:
                mo_map[key] = []
            mo_map[key].append(case)

        for (category, crime_type), c_list in mo_map.items():
            if len(c_list) >= request.minimum_recurrence:
                case_ids = sorted([str(c.id) for c in c_list])
                station_ids = sorted(list({c.station_id for c in c_list if c.station_id}))
                signals = [f"Crime Category: {category}", f"Crime Type: {crime_type}"]
                
                # Check for shared evidence types
                evidence_types = set()
                for c in c_list:
                    for ev in getattr(c, "evidences", []):
                        if getattr(ev, "evidence_type", None):
                            evidence_types.add(ev.evidence_type)
                for et in sorted(list(evidence_types)):
                    signals.append(f"Evidence Type: {et}")

                pat_id = self._generate_pattern_id(PatternType.MODUS_OPERANDI, case_ids, [], signals)
                patterns.append(
                    PatternObservation(
                        pattern_id=pat_id,
                        pattern_type=PatternType.MODUS_OPERANDI,
                        title=f"Recurring Modus Operandi Pattern: {crime_type}",
                        description=f"Identified {len(c_list)} cases sharing matching crime category '{category}' and operational crime type '{crime_type}'.",
                        case_ids=case_ids,
                        entity_ids=[],
                        entity_types=[],
                        station_ids=station_ids,
                        supporting_signals=signals,
                        occurrence_count=len(c_list),
                        structural_strength=round(min(1.0, len(c_list) / 5.0), 4),
                        provenance={
                            "source_cases": case_ids,
                            "crime_category": category,
                            "crime_type": crime_type,
                            "methodology": request.methodology_version,
                        },
                    )
                )
        return patterns

    def _detect_recurring_person_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []
        person_map: Dict[str, Tuple[str, List[Case]]] = {}

        for case in cases:
            for assoc in getattr(case, "person_associations", []):
                person = getattr(assoc, "person", None)
                if person and getattr(person, "id", None):
                    pid = str(person.id)
                    pname = getattr(person, "name", "Unknown Person")
                    if pid not in person_map:
                        person_map[pid] = (pname, [])
                    if case not in person_map[pid][1]:
                        person_map[pid][1].append(case)

        for pid, (pname, c_list) in person_map.items():
            if len(c_list) >= request.minimum_recurrence:
                case_ids = sorted([str(c.id) for c in c_list])
                station_ids = sorted(list({c.station_id for c in c_list if c.station_id}))
                signals = [f"Shared Person Entity: {pname} ({pid})"]

                pat_id = self._generate_pattern_id(PatternType.RECURRING_ENTITY, case_ids, [pid], signals)
                patterns.append(
                    PatternObservation(
                        pattern_id=pat_id,
                        pattern_type=PatternType.RECURRING_ENTITY,
                        title=f"Recurring Person Entity Pattern across {len(c_list)} Cases",
                        description=f"Person entity '{pname}' is associated with {len(c_list)} distinct cases across {len(station_ids)} police station(s).",
                        case_ids=case_ids,
                        entity_ids=[pid],
                        entity_types=["Person"],
                        station_ids=station_ids,
                        supporting_signals=signals,
                        occurrence_count=len(c_list),
                        structural_strength=round(min(1.0, len(c_list) / 4.0), 4),
                        provenance={
                            "person_id": pid,
                            "person_name": pname,
                            "source_cases": case_ids,
                            "methodology": request.methodology_version,
                        },
                    )
                )
        return patterns

    def _detect_recurring_location_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []
        loc_map: Dict[str, Tuple[str, List[Case]]] = {}

        for case in cases:
            loc = getattr(case, "location", None)
            if loc and getattr(loc, "id", None):
                lid = str(loc.id)
                addr = getattr(loc, "address", None) or getattr(loc, "city", "Unknown Location")
                if lid not in loc_map:
                    loc_map[lid] = (addr, [])
                if case not in loc_map[lid][1]:
                    loc_map[lid][1].append(case)

        for lid, (addr, c_list) in loc_map.items():
            if len(c_list) >= request.minimum_recurrence:
                case_ids = sorted([str(c.id) for c in c_list])
                station_ids = sorted(list({c.station_id for c in c_list if c.station_id}))
                signals = [f"Shared Location Entity: {addr} ({lid})"]

                pat_id = self._generate_pattern_id(PatternType.RECURRING_LOCATION, case_ids, [lid], signals)
                patterns.append(
                    PatternObservation(
                        pattern_id=pat_id,
                        pattern_type=PatternType.RECURRING_LOCATION,
                        title=f"Recurring Location Pattern across {len(c_list)} Cases",
                        description=f"Location '{addr}' is associated with {len(c_list)} distinct cases across {len(station_ids)} police station(s).",
                        case_ids=case_ids,
                        entity_ids=[lid],
                        entity_types=["Location"],
                        station_ids=station_ids,
                        supporting_signals=signals,
                        occurrence_count=len(c_list),
                        structural_strength=round(min(1.0, len(c_list) / 4.0), 4),
                        provenance={
                            "location_id": lid,
                            "address": addr,
                            "source_cases": case_ids,
                            "methodology": request.methodology_version,
                        },
                    )
                )
        return patterns

    def _detect_recurring_vehicle_phone_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []
        veh_map: Dict[str, Tuple[str, List[Case]]] = {}
        ph_map: Dict[str, Tuple[str, List[Case]]] = {}

        for case in cases:
            for assoc in getattr(case, "vehicle_associations", []):
                veh = getattr(assoc, "vehicle", None)
                if veh and getattr(veh, "id", None):
                    vid = str(veh.id)
                    reg = getattr(veh, "registration_number", "Unknown Vehicle")
                    if vid not in veh_map:
                        veh_map[vid] = (reg, [])
                    if case not in veh_map[vid][1]:
                        veh_map[vid][1].append(case)

            for assoc in getattr(case, "phone_associations", []):
                ph = getattr(assoc, "phone", None)
                if ph and getattr(ph, "id", None):
                    phid = str(ph.id)
                    num = getattr(ph, "normalized_number", "Unknown Phone")
                    if phid not in ph_map:
                        ph_map[phid] = (num, [])
                    if case not in ph_map[phid][1]:
                        ph_map[phid][1].append(case)

        # Vehicle Patterns
        for vid, (reg, c_list) in veh_map.items():
            if len(c_list) >= request.minimum_recurrence:
                case_ids = sorted([str(c.id) for c in c_list])
                station_ids = sorted(list({c.station_id for c in c_list if c.station_id}))
                signals = [f"Shared Vehicle Entity: {reg} ({vid})"]

                pat_id = self._generate_pattern_id(PatternType.RECURRING_VEHICLE_PHONE, case_ids, [vid], signals)
                patterns.append(
                    PatternObservation(
                        pattern_id=pat_id,
                        pattern_type=PatternType.RECURRING_VEHICLE_PHONE,
                        title=f"Recurring Vehicle Entity Pattern: {reg}",
                        description=f"Vehicle entity '{reg}' is associated with {len(c_list)} distinct cases.",
                        case_ids=case_ids,
                        entity_ids=[vid],
                        entity_types=["Vehicle"],
                        station_ids=station_ids,
                        supporting_signals=signals,
                        occurrence_count=len(c_list),
                        structural_strength=round(min(1.0, len(c_list) / 4.0), 4),
                        provenance={
                            "vehicle_id": vid,
                            "registration_number": reg,
                            "source_cases": case_ids,
                            "methodology": request.methodology_version,
                        },
                    )
                )

        # Phone Patterns
        for phid, (num, c_list) in ph_map.items():
            if len(c_list) >= request.minimum_recurrence:
                case_ids = sorted([str(c.id) for c in c_list])
                station_ids = sorted(list({c.station_id for c in c_list if c.station_id}))
                signals = [f"Shared Phone Entity: {num} ({phid})"]

                pat_id = self._generate_pattern_id(PatternType.RECURRING_VEHICLE_PHONE, case_ids, [phid], signals)
                patterns.append(
                    PatternObservation(
                        pattern_id=pat_id,
                        pattern_type=PatternType.RECURRING_VEHICLE_PHONE,
                        title=f"Recurring Phone Entity Pattern: {num}",
                        description=f"Phone entity '{num}' is associated with {len(c_list)} distinct cases.",
                        case_ids=case_ids,
                        entity_ids=[phid],
                        entity_types=["Phone"],
                        station_ids=station_ids,
                        supporting_signals=signals,
                        occurrence_count=len(c_list),
                        structural_strength=round(min(1.0, len(c_list) / 4.0), 4),
                        provenance={
                            "phone_id": phid,
                            "normalized_number": num,
                            "source_cases": case_ids,
                            "methodology": request.methodology_version,
                        },
                    )
                )

        return patterns

    def _detect_temporal_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []
        if len(cases) < request.minimum_recurrence or not request.temporal_window_days:
            return patterns

        valid_cases = [c for c in cases if getattr(c, "registration_date", None)]
        valid_cases.sort(key=lambda c: (c.registration_date, str(c.id)))

        window_days = request.temporal_window_days

        for i in range(len(valid_cases)):
            cluster = [valid_cases[i]]
            for j in range(i + 1, len(valid_cases)):
                delta_days = (valid_cases[j].registration_date - valid_cases[i].registration_date).days
                if delta_days <= window_days:
                    cluster.append(valid_cases[j])
                else:
                    break

            if len(cluster) >= request.minimum_recurrence:
                case_ids = sorted([str(c.id) for c in cluster])
                station_ids = sorted(list({c.station_id for c in cluster if c.station_id}))
                start_date = cluster[0].registration_date.isoformat()
                end_date = cluster[-1].registration_date.isoformat()

                signals = [f"Temporal Window: {window_days} Days", f"Span: {start_date} to {end_date}"]

                pat_id = self._generate_pattern_id(PatternType.TEMPORAL_CLUSTER, case_ids, [], signals)
                # Check for duplicates
                if not any(p.pattern_id == pat_id for p in patterns):
                    patterns.append(
                        PatternObservation(
                            pattern_id=pat_id,
                            pattern_type=PatternType.TEMPORAL_CLUSTER,
                            title=f"Temporal Recurrence Cluster: {len(cluster)} Cases in {window_days} Days",
                            description=f"Identified {len(cluster)} cases registered within a {window_days}-day temporal window between {start_date} and {end_date}.",
                            case_ids=case_ids,
                            entity_ids=[],
                            entity_types=[],
                            station_ids=station_ids,
                            supporting_signals=signals,
                            occurrence_count=len(cluster),
                            structural_strength=round(min(1.0, len(cluster) / 5.0), 4),
                            provenance={
                                "start_date": start_date,
                                "end_date": end_date,
                                "window_days": window_days,
                                "source_cases": case_ids,
                                "methodology": request.methodology_version,
                            },
                        )
                    )
        return patterns

    def _detect_cross_station_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []
        station_cases: Dict[str, List[Case]] = {}

        for c in cases:
            stn = getattr(c, "station_id", None)
            if stn:
                if stn not in station_cases:
                    station_cases[stn] = []
                station_cases[stn].append(c)

        if len(station_cases) >= 2 and len(cases) >= request.minimum_recurrence:
            case_ids = sorted([str(c.id) for c in cases])
            station_ids = sorted(list(station_cases.keys()))
            signals = [f"Cross-Station Activity: {len(station_ids)} Police Stations"]

            pat_id = self._generate_pattern_id(PatternType.GEOGRAPHIC_CROSS_STATION, case_ids, [], signals)
            patterns.append(
                PatternObservation(
                    pattern_id=pat_id,
                    pattern_type=PatternType.GEOGRAPHIC_CROSS_STATION,
                    title=f"Cross-Station Structural Pattern across {len(station_ids)} Stations",
                    description=f"Identified structural case activity spanning {len(station_ids)} police stations ({', '.join(station_ids)}).",
                    case_ids=case_ids,
                    entity_ids=[],
                    entity_types=[],
                    station_ids=station_ids,
                    supporting_signals=signals,
                    occurrence_count=len(cases),
                    structural_strength=round(min(1.0, len(station_ids) / 4.0), 4),
                    provenance={
                        "police_stations": station_ids,
                        "source_cases": case_ids,
                        "methodology": request.methodology_version,
                    },
                )
            )
        return patterns

    def _detect_case_characteristic_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []
        char_map: Dict[Tuple[str, str, str], List[Case]] = {}

        for c in cases:
            key = (c.crime_category, c.crime_type, c.district)
            if key not in char_map:
                char_map[key] = []
            char_map[key].append(c)

        for (cat, crime_type, dist), c_list in char_map.items():
            if len(c_list) >= request.minimum_recurrence:
                case_ids = sorted([str(c.id) for c in c_list])
                station_ids = sorted(list({c.station_id for c in c_list if c.station_id}))
                signals = [f"Category: {cat}", f"Crime Type: {crime_type}", f"District: {dist}"]

                pat_id = self._generate_pattern_id(PatternType.CASE_CHARACTERISTIC, case_ids, [], signals)
                patterns.append(
                    PatternObservation(
                        pattern_id=pat_id,
                        pattern_type=PatternType.CASE_CHARACTERISTIC,
                        title=f"Structured Case Characteristic Combination: {crime_type} in {dist}",
                        description=f"Identified {len(c_list)} cases sharing matching crime category '{cat}', crime type '{crime_type}', and district '{dist}'.",
                        case_ids=case_ids,
                        entity_ids=[],
                        entity_types=[],
                        station_ids=station_ids,
                        supporting_signals=signals,
                        occurrence_count=len(c_list),
                        structural_strength=round(min(1.0, len(c_list) / 5.0), 4),
                        provenance={
                            "crime_category": cat,
                            "crime_type": crime_type,
                            "district": dist,
                            "source_cases": case_ids,
                            "methodology": request.methodology_version,
                        },
                    )
                )
        return patterns

    def _detect_graph_structural_patterns(self, cases: List[Case], request: PatternDetectionRequest) -> List[PatternObservation]:
        patterns: List[PatternObservation] = []

        # 1. From Community Detection Result (5G)
        if request.community_detection_result:
            for comm in request.community_detection_result.communities:
                if comm.spans_cross_station or comm.density >= 0.2:
                    case_ids = sorted([m.node_id for m in comm.members if m.node_type == "Case"])
                    entity_ids = sorted([m.node_id for m in comm.members if m.node_type != "Case"])
                    entity_types = sorted(list(comm.node_type_distribution.keys()))
                    signals = [f"Community Density: {comm.density}", f"Member Count: {comm.member_count}"]
                    if comm.spans_cross_station:
                        signals.append("Spans Multiple Stations")

                    pat_id = self._generate_pattern_id(PatternType.GRAPH_STRUCTURAL, case_ids, entity_ids, signals)
                    patterns.append(
                        PatternObservation(
                            pattern_id=pat_id,
                            pattern_type=PatternType.GRAPH_STRUCTURAL,
                            title=f"Graph Structural Pattern: Community Cluster ({comm.community_id})",
                            description=f"Identified dense graph community cluster '{comm.community_id}' with {comm.member_count} member nodes and structural density {comm.density}.",
                            case_ids=case_ids,
                            entity_ids=entity_ids,
                            entity_types=entity_types,
                            station_ids=[],
                            supporting_signals=signals,
                            occurrence_count=comm.member_count,
                            structural_strength=round(comm.density, 4),
                            provenance={
                                "community_id": comm.community_id,
                                "density": comm.density,
                                "spans_cross_station": comm.spans_cross_station,
                                "methodology": request.methodology_version,
                            },
                        )
                    )

        # 2. From Network Analytics Result (5F)
        if request.graph_analytics_result:
            connectors = [nm for nm in request.graph_analytics_result.node_metrics if nm.is_connector_node]
            for conn in connectors:
                signals = [f"Connector Role: {conn.connector_role_summary or 'Bridge Node'}"]
                pat_id = self._generate_pattern_id(PatternType.GRAPH_STRUCTURAL, [], [conn.node_id], signals)
                patterns.append(
                    PatternObservation(
                        pattern_id=pat_id,
                        pattern_type=PatternType.GRAPH_STRUCTURAL,
                        title=f"Graph Structural Pattern: Network Connector ({conn.label}:{conn.node_id})",
                        description=f"Identified high-centrality network connector node '{conn.node_id}' ({conn.label}) connecting {conn.connected_case_count} cases.",
                        case_ids=[],
                        entity_ids=[conn.node_id],
                        entity_types=[conn.label],
                        station_ids=[],
                        supporting_signals=signals,
                        occurrence_count=conn.total_degree,
                        structural_strength=round(conn.centrality.betweenness_centrality, 4),
                        provenance={
                            "connector_node_id": conn.node_id,
                            "label": conn.label,
                            "betweenness": conn.centrality.betweenness_centrality,
                            "methodology": request.methodology_version,
                        },
                    )
                )

        return patterns

    # =====================================================================
    # DETERMINISTIC PATTERN ID HELPER
    # =====================================================================

    def _generate_pattern_id(
        self, pattern_type: PatternType, case_ids: List[str], entity_ids: List[str], signals: List[str]
    ) -> str:
        canonical_str = (
            f"{pattern_type.value}:"
            + "|".join(sorted(case_ids))
            + ":"
            + "|".join(sorted(entity_ids))
            + ":"
            + "|".join(sorted(signals))
        )
        digest = hashlib.sha256(canonical_str.encode("utf-8")).hexdigest()[:12]
        return f"pat:{pattern_type.value.lower()}:{digest}"


pattern_intelligence_engine = PatternIntelligenceEngine()
