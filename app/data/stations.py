from typing import Dict, List, TypedDict


class PoliceStationInfo(TypedDict):
    station_id: str
    police_station: str
    district: str
    state: str


POLICE_STATIONS: List[PoliceStationInfo] = [
    {
        "station_id": "PS_BBSR_001",
        "police_station": "Kharavela Nagar PS",
        "district": "Khordha (Bhubaneswar)",
        "state": "Odisha",
    },
    {
        "station_id": "PS_BBSR_002",
        "police_station": "Saheed Nagar PS",
        "district": "Khordha (Bhubaneswar)",
        "state": "Odisha",
    },
    {
        "station_id": "PS_BBSR_003",
        "police_station": "Mancheswar PS",
        "district": "Khordha (Bhubaneswar)",
        "state": "Odisha",
    },
    {
        "station_id": "PS_BBSR_004",
        "police_station": "Chandrasekharpur PS",
        "district": "Khordha (Bhubaneswar)",
        "state": "Odisha",
    },
    {
        "station_id": "PS_CTC_001",
        "police_station": "Cuttack Sadar PS",
        "district": "Cuttack",
        "state": "Odisha",
    },
    {
        "station_id": "PS_PURI_001",
        "police_station": "Puri Town PS",
        "district": "Puri",
        "state": "Odisha",
    },
    {
        "station_id": "PS_SBP_001",
        "police_station": "Sambalpur Town PS",
        "district": "Sambalpur",
        "state": "Odisha",
    },
    {
        "station_id": "PS_RKL_001",
        "police_station": "Rourkela PS",
        "district": "Sundargarh",
        "state": "Odisha",
    },
]

STATION_LOOKUP: Dict[str, PoliceStationInfo] = {
    s["station_id"]: s for s in POLICE_STATIONS
}
