import re
from datetime import date, datetime, time
from typing import Any, Dict, List, Optional
from app.models.case import Case
from app.normalization.service import EntityNormalizationService
from app.services.case_similarity.models import (
    CaseIdentityFeatures,
    CrimeCharacteristicsFeatures,
    ExtractedCaseFeatures,
    ExtractedEvidenceEntity,
    ExtractedPersonEntity,
    ExtractedPhoneEntity,
    ExtractedVehicleEntity,
    GeographicCharacteristicsFeatures,
    LegalCharacteristicsFeatures,
    LinkedEntitiesFeatures,
    MOSourceType,
    TemporalFeatures,
)


def get_time_of_day_bucket(hour: Optional[int]) -> Optional[str]:
    """Helper to classify hour into standard time-of-day buckets."""
    if hour is None:
        return None
    if 6 <= hour < 12:
        return "MORNING"
    elif 12 <= hour < 17:
        return "AFTERNOON"
    elif 17 <= hour < 21:
        return "EVENING"
    elif 0 <= hour < 6 or 21 <= hour <= 23:
        return "NIGHT"
    return None


def normalize_legal_section_code(item: Any) -> tuple[str, str]:
    """Extracts (raw_code, normalized_section) preserving exact law name (IPC, BNS, IT_ACT, etc.)."""
    if isinstance(item, dict):
        code = str(item.get("code") or item.get("section") or "").strip()
        law = str(item.get("law_name") or item.get("law") or "").strip()
        if law and code:
            return code, f"{law}_{code}"
        elif code:
            return code, code
        return "", ""

    s = str(item).strip()
    if not s:
        return "", ""

    # Parse strings like "BNS 303", "IPC 379", "BNS_303", "379"
    match = re.match(r"^([A-Za-z_]+)[\s_]+(.+)$", s)
    if match:
        law_part, code_part = match.groups()
        return code_part, f"{law_part.upper()}_{code_part}"

    return s, s


class CaseFeatureExtractor:
    """Deterministic, production-ready Case Feature Extractor for S.I.R.I.S. Central Intelligence Engine."""

    @classmethod
    def extract_from_model(cls, case: Case) -> ExtractedCaseFeatures:
        """Extracts normalized features from an active SQLAlchemy Case domain model instance."""
        # 1. Identity Features
        identity = CaseIdentityFeatures(
            case_id=str(case.id),
            fir_number=case.fir_number,
            station_id=case.station_id,
            police_station=case.police_station,
            district=case.district,
            state=case.state,
            registration_date=str(case.registration_date) if case.registration_date else None,
            incident_date=str(case.incident_date) if case.incident_date else None,
            status=case.status
        )

        # 2. MO Derivation & Crime Characteristics
        dedicated_mo = getattr(case, "modus_operandi", None)
        desc = case.description

        if dedicated_mo and str(dedicated_mo).strip():
            raw_mo = str(dedicated_mo).strip()
            mo_source = MOSourceType.DEDICATED_MO
        elif desc and str(desc).strip():
            raw_mo = str(desc).strip()
            mo_source = MOSourceType.DESCRIPTION_DERIVED
        else:
            raw_mo = None
            mo_source = MOSourceType.UNAVAILABLE

        norm_mo = EntityNormalizationService.normalize_mo(raw_mo)

        crime = CrimeCharacteristicsFeatures(
            crime_type=case.crime_type,
            crime_category=case.crime_category,
            description=desc,
            raw_mo=raw_mo,
            mo_source=mo_source,
            normalized_mo_tokens=norm_mo.tokens,
            mo_keywords=[t for t in norm_mo.tokens if len(t) >= 4]
        )

        # 3. Legal Characteristics
        legal_sections: List[str] = []
        normalized_sections: List[str] = []
        if hasattr(case, "legal_section_associations") and case.legal_section_associations:
            for assoc in case.legal_section_associations:
                if assoc.legal_section:
                    sec_code = assoc.legal_section.code
                    law_name = assoc.legal_section.law_name or "IPC"
                    legal_sections.append(sec_code)
                    normalized_sections.append(f"{law_name}_{sec_code}")

        legal = LegalCharacteristicsFeatures(
            legal_sections=legal_sections,
            normalized_sections=normalized_sections
        )

        # 4. Geographic Characteristics
        loc_obj = getattr(case, "location", None)
        geo_address = loc_obj.address if loc_obj else None
        geo_locality = loc_obj.locality if loc_obj else None
        geo_city = loc_obj.city if loc_obj else None
        geo_district = loc_obj.district if loc_obj else case.district
        geo_state = loc_obj.state if loc_obj else case.state
        geo_lat = loc_obj.latitude if loc_obj else None
        geo_lon = loc_obj.longitude if loc_obj else None

        raw_loc_str = " ".join([x for x in [geo_locality, geo_address, geo_district] if x])
        norm_loc = EntityNormalizationService.normalize_location(raw_loc_str) if raw_loc_str.strip() else None

        geographic = GeographicCharacteristicsFeatures(
            address=geo_address,
            locality=geo_locality,
            city=geo_city,
            district=geo_district,
            state=geo_state,
            latitude=geo_lat,
            longitude=geo_lon,
            normalized_location_text=norm_loc.normalized_value if norm_loc else None,
            location_tokens=norm_loc.tokens if norm_loc else []
        )

        # 5. Linked Entities
        persons: List[ExtractedPersonEntity] = []
        if hasattr(case, "person_associations") and case.person_associations:
            for passoc in case.person_associations:
                p = passoc.person
                if p:
                    norm_p = EntityNormalizationService.normalize_person(p.name)
                    role_str = passoc.role.value if hasattr(passoc.role, "value") else str(passoc.role)
                    persons.append(
                        ExtractedPersonEntity(
                            person_id=str(p.id),
                            name=p.name,
                            normalized_name=norm_p.normalized_value,
                            phonetic_name=norm_p.phonetic_value,
                            role=role_str,
                            gender=p.gender,
                            date_of_birth=str(p.date_of_birth) if p.date_of_birth else None
                        )
                    )

        vehicles: List[ExtractedVehicleEntity] = []
        if hasattr(case, "vehicle_associations") and case.vehicle_associations:
            for vasoc in case.vehicle_associations:
                v = vasoc.vehicle
                if v:
                    norm_v = EntityNormalizationService.normalize_vehicle(v.registration_number)
                    role_str = vasoc.role.value if hasattr(vasoc.role, "value") else str(vasoc.role)
                    vehicles.append(
                        ExtractedVehicleEntity(
                            vehicle_id=str(v.id),
                            registration_number=v.registration_number,
                            normalized_reg=norm_v.normalized_value,
                            role=role_str,
                            vehicle_type=v.vehicle_type,
                            make=v.make,
                            model=v.model
                        )
                    )

        phones: List[ExtractedPhoneEntity] = []
        if hasattr(case, "phone_associations") and case.phone_associations:
            for phasoc in case.phone_associations:
                ph = phasoc.phone
                if ph:
                    norm_ph = EntityNormalizationService.normalize_phone(ph.normalized_number)
                    phones.append(
                        ExtractedPhoneEntity(
                            phone_id=str(ph.id),
                            raw_number=ph.normalized_number,
                            normalized_e164=norm_ph.normalized_value,
                            is_valid=norm_ph.metadata.get("is_valid", True)
                        )
                    )

        evidence_list: List[ExtractedEvidenceEntity] = []
        if hasattr(case, "evidences") and case.evidences:
            for ev in case.evidences:
                norm_ev = EntityNormalizationService.normalize_evidence(ev.description)
                ev_type_str = ev.evidence_type.value if hasattr(ev.evidence_type, "value") else str(ev.evidence_type)
                evidence_list.append(
                    ExtractedEvidenceEntity(
                        evidence_id=str(ev.id),
                        evidence_type=ev_type_str,
                        description=ev.description,
                        normalized_tokens=norm_ev.tokens
                    )
                )

        entities = LinkedEntitiesFeatures(
            persons=persons,
            vehicles=vehicles,
            phones=phones,
            evidence=evidence_list
        )

        # 6. Temporal Features
        dt_val = case.incident_date
        t_val = case.incident_time
        inc_dt_str = None
        yr = None
        mo_num = None
        dow = None
        hr = None

        if dt_val:
            yr = dt_val.year
            mo_num = dt_val.month
            dow = dt_val.weekday()
            inc_dt_str = str(dt_val)

        if t_val:
            hr = t_val.hour

        tod = get_time_of_day_bucket(hr)

        temporal = TemporalFeatures(
            incident_datetime=f"{inc_dt_str}T{t_val}" if (inc_dt_str and t_val) else inc_dt_str,
            incident_date=inc_dt_str,
            year=yr,
            month=mo_num,
            day_of_week=dow,
            hour=hr,
            time_of_day_bucket=tod
        )

        return ExtractedCaseFeatures(
            identity=identity,
            crime=crime,
            legal=legal,
            geographic=geographic,
            entities=entities,
            temporal=temporal
        )

    @classmethod
    def extract_from_dict(cls, c_dict: Dict[str, Any]) -> ExtractedCaseFeatures:
        """Extracts normalized features from a case dictionary without inventing fabricated defaults."""
        cid = c_dict.get("id") or c_dict.get("case_id")
        if not cid or not str(cid).strip():
            raise ValueError("case_id is required for feature extraction")

        fir = c_dict.get("fir_number")
        if not fir or not str(fir).strip():
            raise ValueError("fir_number is required for feature extraction")

        identity = CaseIdentityFeatures(
            case_id=str(cid).strip(),
            fir_number=str(fir).strip(),
            station_id=str(c_dict["station_id"]).strip() if c_dict.get("station_id") else None,
            police_station=str(c_dict["police_station"]).strip() if c_dict.get("police_station") else None,
            district=str(c_dict["district"]).strip() if c_dict.get("district") else None,
            state=str(c_dict["state"]).strip() if c_dict.get("state") else None,
            registration_date=str(c_dict["registration_date"]).strip() if c_dict.get("registration_date") else None,
            incident_date=str(c_dict["incident_date"]).strip() if c_dict.get("incident_date") else None,
            status=str(c_dict["status"]).strip() if c_dict.get("status") else None
        )

        # MO Derivation
        dedicated_mo = c_dict.get("modus_operandi") or c_dict.get("mo")
        desc = c_dict.get("description")

        if dedicated_mo and str(dedicated_mo).strip():
            raw_mo = str(dedicated_mo).strip()
            mo_source = MOSourceType.DEDICATED_MO
        elif desc and str(desc).strip():
            raw_mo = str(desc).strip()
            mo_source = MOSourceType.DESCRIPTION_DERIVED
        else:
            raw_mo = None
            mo_source = MOSourceType.UNAVAILABLE

        norm_mo = EntityNormalizationService.normalize_mo(raw_mo) if raw_mo else None

        crime = CrimeCharacteristicsFeatures(
            crime_type=str(c_dict["crime_type"]).strip() if c_dict.get("crime_type") else None,
            crime_category=str(c_dict["crime_category"]).strip() if c_dict.get("crime_category") else None,
            description=str(desc).strip() if desc else None,
            raw_mo=raw_mo,
            mo_source=mo_source,
            normalized_mo_tokens=norm_mo.tokens if norm_mo else [],
            mo_keywords=[t for t in norm_mo.tokens if len(t) >= 4] if norm_mo else []
        )

        # Legal Sections Preservation (BNS, IPC, IT_ACT, etc.)
        legal_raw = c_dict.get("legal_sections") or []
        legal_sections = []
        normalized_sections = []

        for item in legal_raw:
            raw_code, norm_sec = normalize_legal_section_code(item)
            if raw_code:
                legal_sections.append(raw_code)
            if norm_sec:
                normalized_sections.append(norm_sec)

        legal = LegalCharacteristicsFeatures(
            legal_sections=legal_sections,
            normalized_sections=normalized_sections
        )

        # Geographic Characteristics
        addr = c_dict.get("address")
        locality = c_dict.get("locality")
        city = c_dict.get("city")
        district = c_dict.get("district")
        state = c_dict.get("state")
        lat = c_dict.get("latitude")
        lon = c_dict.get("longitude")

        raw_loc_str = " ".join([str(x).strip() for x in [locality, addr, district] if x and str(x).strip()])
        norm_loc = EntityNormalizationService.normalize_location(raw_loc_str) if raw_loc_str else None

        geographic = GeographicCharacteristicsFeatures(
            address=str(addr).strip() if addr else None,
            locality=str(locality).strip() if locality else None,
            city=str(city).strip() if city else None,
            district=str(district).strip() if district else None,
            state=str(state).strip() if state else None,
            latitude=float(lat) if lat is not None else None,
            longitude=float(lon) if lon is not None else None,
            normalized_location_text=norm_loc.normalized_value if norm_loc else None,
            location_tokens=norm_loc.tokens if norm_loc else []
        )

        # Linked Entities
        persons = []
        for p in c_dict.get("persons") or []:
            name = p.get("name") if isinstance(p, dict) else str(p)
            norm_p = EntityNormalizationService.normalize_person(name)
            pid = p.get("id", "p1") if isinstance(p, dict) else "p1"
            role = p.get("role", "OTHER") if isinstance(p, dict) else "OTHER"
            persons.append(
                ExtractedPersonEntity(
                    person_id=str(pid),
                    name=name,
                    normalized_name=norm_p.normalized_value,
                    phonetic_name=norm_p.phonetic_value,
                    role=role,
                    gender=p.get("gender") if isinstance(p, dict) else None,
                    date_of_birth=str(p.get("date_of_birth")) if (isinstance(p, dict) and p.get("date_of_birth")) else None
                )
            )

        vehicles = []
        for v in c_dict.get("vehicles") or []:
            reg = v.get("registration_number") if isinstance(v, dict) else str(v)
            norm_v = EntityNormalizationService.normalize_vehicle(reg)
            vid = v.get("id", "v1") if isinstance(v, dict) else "v1"
            vehicles.append(
                ExtractedVehicleEntity(
                    vehicle_id=str(vid),
                    registration_number=reg,
                    normalized_reg=norm_v.normalized_value
                )
            )

        phones = []
        for ph in c_dict.get("phones") or []:
            num = ph.get("normalized_number") or ph.get("number") if isinstance(ph, dict) else str(ph)
            norm_ph = EntityNormalizationService.normalize_phone(num)
            phid = ph.get("id", "ph1") if isinstance(ph, dict) else "ph1"
            phones.append(
                ExtractedPhoneEntity(
                    phone_id=str(phid),
                    raw_number=num,
                    normalized_e164=norm_ph.normalized_value,
                    is_valid=norm_ph.metadata.get("is_valid", True)
                )
            )

        evidence_list = []
        for ev in c_dict.get("evidences") or c_dict.get("evidence") or []:
            ev_desc = ev.get("description") if isinstance(ev, dict) else str(ev)
            ev_type = ev.get("evidence_type", "OTHER") if isinstance(ev, dict) else "OTHER"
            norm_ev = EntityNormalizationService.normalize_evidence(ev_desc)
            evid = ev.get("id", "ev1") if isinstance(ev, dict) else "ev1"
            evidence_list.append(
                ExtractedEvidenceEntity(
                    evidence_id=str(evid),
                    evidence_type=ev_type,
                    description=ev_desc,
                    normalized_tokens=norm_ev.tokens
                )
            )

        entities = LinkedEntitiesFeatures(
            persons=persons,
            vehicles=vehicles,
            phones=phones,
            evidence=evidence_list
        )

        inc_dt = c_dict.get("incident_date")
        yr = None
        mo_num = None
        dow = None
        if inc_dt:
            if isinstance(inc_dt, date):
                yr = inc_dt.year
                mo_num = inc_dt.month
                dow = inc_dt.weekday()
            elif isinstance(inc_dt, str) and len(inc_dt) >= 10:
                try:
                    d_parsed = datetime.strptime(inc_dt[:10], "%Y-%m-%d")
                    yr = d_parsed.year
                    mo_num = d_parsed.month
                    dow = d_parsed.weekday()
                except ValueError:
                    pass

        hr = c_dict.get("hour")
        if hr is not None:
            try:
                hr = int(hr)
            except (ValueError, TypeError):
                hr = None

        tod = get_time_of_day_bucket(hr)

        temporal = TemporalFeatures(
            incident_date=str(inc_dt) if inc_dt else None,
            year=yr,
            month=mo_num,
            day_of_week=dow,
            hour=hr,
            time_of_day_bucket=tod
        )

        return ExtractedCaseFeatures(
            identity=identity,
            crime=crime,
            legal=legal,
            geographic=geographic,
            entities=entities,
            temporal=temporal
        )
