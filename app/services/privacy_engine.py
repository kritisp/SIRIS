import re
import logging
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple
from pydantic import BaseModel, ConfigDict, Field

from app.models.case import Case
from app.services.explainability_engine import ExplainabilityAssessment, ExplainabilityResult

logger = logging.getLogger(__name__)

LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION = "llm-privacy-boundary-v1"

# Regex patterns for auto-detecting PII in text strings
PHONE_PATTERN = re.compile(r"(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}")
EMAIL_PATTERN = re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}")
VEHICLE_REG_PATTERN = re.compile(r"\b[A-Z]{2}[0-9]{1,2}[A-Z]{1,3}[0-9]{4}\b")
GOVT_ID_PATTERN = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}\b|\b[A-Z]{5}[0-9]{4}[A-Z]{1}\b")
UUID_PATTERN = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


# =====================================================================
# 1. PII TAXONOMY & CONTRACTS
# =====================================================================

class PIIEntityType(str, Enum):
    """Supported sensitive personal identifier categories."""

    PERSON_NAME = "PERSON_NAME"
    PHONE_NUMBER = "PHONE_NUMBER"
    VEHICLE_REGISTRATION = "VEHICLE_REGISTRATION"
    EMAIL_ADDRESS = "EMAIL_ADDRESS"
    GOVERNMENT_ID = "GOVERNMENT_ID"
    CASE_IDENTIFIER = "CASE_IDENTIFIER"
    PERSONAL_IDENTIFIER = "PERSONAL_IDENTIFIER"
    SENSITIVE_ENTITY_IDENTIFIER = "SENSITIVE_ENTITY_IDENTIFIER"


class MaskedIdentifier(BaseModel):
    """Private association between a type-scoped alias and original PII."""

    alias: str
    entity_type: PIIEntityType
    original_value: str
    provenance: Dict[str, Any] = Field(default_factory=dict)


class DeidentificationMapping(BaseModel):
    """Private, application-side PII mapping container. NEVER exposed to LLM."""

    alias_to_original: Dict[str, str] = Field(default_factory=dict)
    original_to_alias: Dict[str, str] = Field(default_factory=dict)
    entity_types: Dict[str, PIIEntityType] = Field(default_factory=dict)
    methodology_version: str = LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION


class LLMSafeExplainabilityAssessment(BaseModel):
    """Sanitized, LLM-safe explanation assessment payload."""

    explanation_id: str
    subject_alias: str
    subject_type: str
    title: str
    observation: str
    explanation: str
    supporting_case_aliases: List[str] = Field(default_factory=list)
    supporting_entity_aliases: List[str] = Field(default_factory=list)
    supporting_relationship_ids: List[str] = Field(default_factory=list)
    supporting_pattern_ids: List[str] = Field(default_factory=list)
    supporting_community_ids: List[str] = Field(default_factory=list)
    supporting_connector_ids: List[str] = Field(default_factory=list)
    evidence_items: List[Dict[str, Any]] = Field(default_factory=list)
    contributing_signals: List[Dict[str, Any]] = Field(default_factory=list)
    confidence_reference: Optional[Dict[str, Any]] = None
    limitations: List[str] = Field(default_factory=list)
    preserved_analytical_context: Dict[str, Any] = Field(default_factory=dict)
    methodology_version: str = LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION


class LLMSafeExplainabilityPayload(BaseModel):
    """Top-level LLM-safe structured payload containing ZERO raw PII."""

    total_explanations: int
    explanations: List[LLMSafeExplainabilityAssessment] = Field(default_factory=list)
    preserved_global_context: Dict[str, Any] = Field(default_factory=dict)
    methodology_version: str = LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION


class DeidentificationResult(BaseModel):
    """Overall result separating LLM-safe payload from private mapping."""

    llm_safe_payload: LLMSafeExplainabilityPayload
    private_mapping: DeidentificationMapping
    methodology_version: str = LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION


# =====================================================================
# 2. PII PRIVACY BOUNDARY ENGINE
# =====================================================================

class PIIPrivacyBoundaryEngine:
    """Deterministic, application-side PII De-identification Engine."""

    def __init__(self) -> None:
        self._type_prefixes: Dict[PIIEntityType, str] = {
            PIIEntityType.PERSON_NAME: "Person",
            PIIEntityType.PHONE_NUMBER: "Phone",
            PIIEntityType.VEHICLE_REGISTRATION: "Vehicle",
            PIIEntityType.EMAIL_ADDRESS: "Email",
            PIIEntityType.GOVERNMENT_ID: "ID",
            PIIEntityType.CASE_IDENTIFIER: "Case",
            PIIEntityType.PERSONAL_IDENTIFIER: "ID",
            PIIEntityType.SENSITIVE_ENTITY_IDENTIFIER: "Entity",
        }

    def deidentify_explainability_result(
        self,
        explainability_result: ExplainabilityResult,
        cases: Optional[List[Case]] = None,
    ) -> DeidentificationResult:
        """Transforms ExplainabilityResult into an LLM-safe payload and private mapping."""
        mapping = DeidentificationMapping()
        counters: Dict[str, int] = {}

        # 1. Register domain entity PII from cases if provided
        if cases:
            for case in cases:
                case_id_str = str(case.id)
                self._get_or_create_alias(case_id_str, PIIEntityType.CASE_IDENTIFIER, mapping, counters)
                if case.fir_number:
                    self._get_or_create_alias(case.fir_number, PIIEntityType.CASE_IDENTIFIER, mapping, counters)

                for assoc in getattr(case, "person_associations", []):
                    p = getattr(assoc, "person", None)
                    if p:
                        p_alias = None
                        if getattr(p, "id", None):
                            p_alias = self._get_or_create_alias(str(p.id), PIIEntityType.PERSON_NAME, mapping, counters)
                        if getattr(p, "name", None) and p.name:
                            if p_alias:
                                mapping.original_to_alias[p.name] = p_alias
                                mapping.alias_to_original[p_alias] = p.name  # Prefer human-readable name for backmapping
                            else:
                                self._get_or_create_alias(p.name, PIIEntityType.PERSON_NAME, mapping, counters)

                for assoc in getattr(case, "vehicle_associations", []):
                    v = getattr(assoc, "vehicle", None)
                    if v:
                        v_alias = None
                        if getattr(v, "id", None):
                            v_alias = self._get_or_create_alias(str(v.id), PIIEntityType.VEHICLE_REGISTRATION, mapping, counters)
                        if getattr(v, "registration_number", None) and v.registration_number:
                            if v_alias:
                                mapping.original_to_alias[v.registration_number] = v_alias
                                mapping.alias_to_original[v_alias] = v.registration_number  # Prefer registration number
                            else:
                                self._get_or_create_alias(v.registration_number, PIIEntityType.VEHICLE_REGISTRATION, mapping, counters)

                for assoc in getattr(case, "phone_associations", []):
                    ph = getattr(assoc, "phone", None)
                    if ph:
                        ph_alias = None
                        if getattr(ph, "id", None):
                            ph_alias = self._get_or_create_alias(str(ph.id), PIIEntityType.PHONE_NUMBER, mapping, counters)
                        if getattr(ph, "normalized_number", None) and ph.normalized_number:
                            if ph_alias:
                                mapping.original_to_alias[ph.normalized_number] = ph_alias
                                mapping.alias_to_original[ph_alias] = ph.normalized_number  # Prefer phone number
                            else:
                                self._get_or_create_alias(ph.normalized_number, PIIEntityType.PHONE_NUMBER, mapping, counters)

        # 2. Process Assessments
        llm_assessments: List[LLMSafeExplainabilityAssessment] = []

        for exp in explainability_result.explanations:
            subject_alias = self._mask_identifier_or_text(exp.subject_id, exp.subject_type, mapping, counters)

            case_aliases = [
                self._mask_identifier_or_text(cid, "Case", mapping, counters)
                for cid in exp.supporting_case_ids
            ]
            entity_aliases = [
                self._mask_identifier_or_text(eid, exp.subject_type, mapping, counters)
                for eid in exp.supporting_entity_ids
            ]

            title_masked = self._mask_pii_in_text(exp.title, mapping, counters)
            obs_masked = self._mask_pii_in_text(exp.observation, mapping, counters)
            exp_text_masked = self._mask_pii_in_text(exp.explanation, mapping, counters)
            limitations_masked = [
                self._mask_pii_in_text(lim, mapping, counters)
                for lim in exp.limitations
            ]

            evidence_items_masked = []
            for item in exp.evidence_items:
                item_dict = item.model_dump()
                item_dict["title"] = self._mask_pii_in_text(item_dict.get("title", ""), mapping, counters)
                item_dict["description"] = self._mask_pii_in_text(item_dict.get("description", ""), mapping, counters)
                item_dict["source_id"] = self._mask_identifier_or_text(item_dict.get("source_id", ""), item_dict.get("source_type", ""), mapping, counters)
                item_dict["provenance"] = self._mask_pii_in_value(item_dict.get("provenance", {}), mapping, counters)
                
                signals_in_item = []
                for sig in item_dict.get("supporting_signals", []):
                    sig["signal_summary"] = self._mask_pii_in_text(sig.get("signal_summary", ""), mapping, counters)
                    sig["provenance"] = self._mask_pii_in_value(sig.get("provenance", {}), mapping, counters)
                    signals_in_item.append(sig)
                item_dict["supporting_signals"] = signals_in_item
                evidence_items_masked.append(item_dict)

            signals_masked = []
            for sig in exp.contributing_signals:
                sig_dict = sig.model_dump()
                sig_dict["signal_summary"] = self._mask_pii_in_text(sig_dict.get("signal_summary", ""), mapping, counters)
                sig_dict["provenance"] = self._mask_pii_in_value(sig_dict.get("provenance", {}), mapping, counters)
                signals_masked.append(sig_dict)

            context = {
                "station_ids": exp.provenance.get("police_stations") or exp.provenance.get("station_ids") or [],
                "district": exp.provenance.get("district"),
                "crime_category": exp.provenance.get("crime_category"),
                "crime_type": exp.provenance.get("crime_type"),
                "density": exp.provenance.get("density"),
                "betweenness": exp.provenance.get("betweenness"),
            }

            llm_assessments.append(
                LLMSafeExplainabilityAssessment(
                    explanation_id=exp.explanation_id,
                    subject_alias=subject_alias,
                    subject_type=exp.subject_type,
                    title=title_masked,
                    observation=obs_masked,
                    explanation=exp_text_masked,
                    supporting_case_aliases=sorted(list(set(case_aliases))),
                    supporting_entity_aliases=sorted(list(set(entity_aliases))),
                    supporting_relationship_ids=exp.supporting_relationship_ids,
                    supporting_pattern_ids=exp.supporting_pattern_ids,
                    supporting_community_ids=exp.supporting_community_ids,
                    supporting_connector_ids=exp.supporting_connector_ids,
                    evidence_items=evidence_items_masked,
                    contributing_signals=signals_masked,
                    confidence_reference=exp.confidence_reference,
                    limitations=limitations_masked,
                    preserved_analytical_context={k: v for k, v in context.items() if v is not None},
                    methodology_version=LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION,
                )
            )

        payload = LLMSafeExplainabilityPayload(
            total_explanations=len(llm_assessments),
            explanations=llm_assessments,
            preserved_global_context={"total_evaluated": len(llm_assessments)},
            methodology_version=LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION,
        )

        return DeidentificationResult(
            llm_safe_payload=payload,
            private_mapping=mapping,
            methodology_version=LLM_PRIVACY_BOUNDARY_METHODOLOGY_VERSION,
        )

    # =====================================================================
    # PRIVATE MASKING HELPERS
    # =====================================================================

    def _get_or_create_alias(
        self,
        value: str,
        entity_type: PIIEntityType,
        mapping: DeidentificationMapping,
        counters: Dict[str, int],
    ) -> str:
        val_str = str(value).strip()
        if not val_str:
            return val_str

        if val_str in mapping.original_to_alias:
            return mapping.original_to_alias[val_str]

        prefix = self._type_prefixes.get(entity_type, "Entity")
        cnt = counters.get(prefix, 0) + 1
        counters[prefix] = cnt

        # Letter indexing: A, B, C, ... Z, AA, AB ...
        alias_suffix = self._int_to_letter(cnt)
        alias = f"{prefix}-{alias_suffix}"

        mapping.original_to_alias[val_str] = alias
        mapping.alias_to_original[alias] = val_str
        mapping.entity_types[alias] = entity_type

        return alias

    def _mask_identifier_or_text(
        self,
        val: str,
        subject_type: str,
        mapping: DeidentificationMapping,
        counters: Dict[str, int],
    ) -> str:
        if not val:
            return val

        if val in mapping.original_to_alias:
            return mapping.original_to_alias[val]

        # Map by type
        lower_type = subject_type.lower()
        if "person" in lower_type:
            return self._get_or_create_alias(val, PIIEntityType.PERSON_NAME, mapping, counters)
        elif "vehicle" in lower_type:
            return self._get_or_create_alias(val, PIIEntityType.VEHICLE_REGISTRATION, mapping, counters)
        elif "phone" in lower_type:
            return self._get_or_create_alias(val, PIIEntityType.PHONE_NUMBER, mapping, counters)
        elif "email" in lower_type:
            return self._get_or_create_alias(val, PIIEntityType.EMAIL_ADDRESS, mapping, counters)
        elif "case" in lower_type:
            return self._get_or_create_alias(val, PIIEntityType.CASE_IDENTIFIER, mapping, counters)

        # UUID check
        if UUID_PATTERN.match(val):
            return self._get_or_create_alias(val, PIIEntityType.SENSITIVE_ENTITY_IDENTIFIER, mapping, counters)

        return self._mask_pii_in_text(val, mapping, counters)

    def _mask_pii_in_text(
        self,
        text: str,
        mapping: DeidentificationMapping,
        counters: Dict[str, int],
    ) -> str:
        if not text:
            return text

        masked_text = text

        # Replace existing mapped originals first
        for orig, alias in sorted(mapping.original_to_alias.items(), key=lambda x: -len(x[0])):
            if orig in masked_text:
                masked_text = masked_text.replace(orig, alias)

        # Detect Phone
        for m in PHONE_PATTERN.finditer(masked_text):
            raw = m.group(0)
            if not raw.startswith("Phone-"):
                alias = self._get_or_create_alias(raw, PIIEntityType.PHONE_NUMBER, mapping, counters)
                masked_text = masked_text.replace(raw, alias)

        # Detect Email
        for m in EMAIL_PATTERN.finditer(masked_text):
            raw = m.group(0)
            if not raw.startswith("Email-"):
                alias = self._get_or_create_alias(raw, PIIEntityType.EMAIL_ADDRESS, mapping, counters)
                masked_text = masked_text.replace(raw, alias)

        # Detect Vehicle Reg
        for m in VEHICLE_REG_PATTERN.finditer(masked_text):
            raw = m.group(0)
            if not raw.startswith("Vehicle-"):
                alias = self._get_or_create_alias(raw, PIIEntityType.VEHICLE_REGISTRATION, mapping, counters)
                masked_text = masked_text.replace(raw, alias)

        # Detect Govt ID
        for m in GOVT_ID_PATTERN.finditer(masked_text):
            raw = m.group(0)
            if not raw.startswith("ID-"):
                alias = self._get_or_create_alias(raw, PIIEntityType.GOVERNMENT_ID, mapping, counters)
                masked_text = masked_text.replace(raw, alias)

        # Detect UUIDs
        for m in UUID_PATTERN.finditer(masked_text):
            raw = m.group(0)
            if not any(raw in a for a in mapping.alias_to_original.keys()):
                alias = self._get_or_create_alias(raw, PIIEntityType.SENSITIVE_ENTITY_IDENTIFIER, mapping, counters)
                masked_text = masked_text.replace(raw, alias)

        return masked_text

    def _mask_pii_in_value(
        self,
        val: Any,
        mapping: DeidentificationMapping,
        counters: Dict[str, int],
    ) -> Any:
        if isinstance(val, str):
            return self._mask_pii_in_text(val, mapping, counters)
        elif isinstance(val, list):
            return [self._mask_pii_in_value(item, mapping, counters) for item in val]
        elif isinstance(val, dict):
            return {k: self._mask_pii_in_value(v, mapping, counters) for k, v in val.items()}
        return val

    def _int_to_letter(self, n: int) -> str:
        result = []
        while n > 0:
            n, remainder = divmod(n - 1, 26)
            result.append(chr(65 + remainder))
        return "".join(reversed(result))


pii_privacy_boundary_engine = PIIPrivacyBoundaryEngine()


# =====================================================================
# 3. PII BACK-MAPPING ENGINE
# =====================================================================

class PIIBackmappingEngine:
    """Deterministic, application-side PII Back-mapping Engine restoring original PII into validated LLM outputs."""

    def backmap_llm_text(self, llm_text: str, private_mapping: DeidentificationMapping) -> str:
        """Restores original PII values for known aliases inside LLM output text."""
        if not llm_text or not private_mapping.alias_to_original:
            return llm_text

        restored = llm_text

        # Sort aliases by length descending to avoid partial token replacement (e.g. Person-AA vs Person-A)
        sorted_aliases = sorted(private_mapping.alias_to_original.keys(), key=lambda a: -len(a))

        for alias in sorted_aliases:
            orig = private_mapping.alias_to_original[alias]
            # Match word boundary token for alias
            pattern = re.compile(r"\b" + re.escape(alias) + r"\b")
            restored = pattern.sub(orig, restored)

        return restored

    def backmap_llm_payload(
        self, payload_dict: Dict[str, Any], private_mapping: DeidentificationMapping
    ) -> Dict[str, Any]:
        """Recursively back-maps aliases in a structured LLM output payload dictionary."""
        if not payload_dict or not private_mapping.alias_to_original:
            return payload_dict

        def _recursive_backmap(val: Any) -> Any:
            if isinstance(val, str):
                return self.backmap_llm_text(val, private_mapping)
            elif isinstance(val, list):
                return [_recursive_backmap(item) for item in val]
            elif isinstance(val, dict):
                return {k: _recursive_backmap(v) for k, v in val.items()}
            return val

        return _recursive_backmap(payload_dict)


pii_backmapper = PIIBackmappingEngine()
