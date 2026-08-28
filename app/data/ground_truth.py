from typing import Dict, List, Any

# Ground truth metadata repository for planted crime clusters
GROUND_TRUTH_CLUSTERS: Dict[str, Dict[str, Any]] = {
    "CLUSTER_A_VEHICLE_NETWORK": {
        "cluster_id": "CLUSTER_A_VEHICLE_NETWORK",
        "description": "Multi-station vehicle theft syndicate operating across Bhubaneswar and Cuttack",
        "station_ids": ["PS_BBSR_001", "PS_BBSR_002", "PS_CTC_001"],
        "expected_relationships": [
            "SHARED_PERSON",
            "SHARED_VEHICLE",
            "SHARED_PHONE",
            "CROSS_STATION_LINKAGE"
        ],
    },
    "CLUSTER_B_BURGLARY_PATTERN": {
        "cluster_id": "CLUSTER_B_BURGLARY_PATTERN",
        "description": "Residential night burglary pattern involving hydraulic cutter entry method",
        "station_ids": ["PS_BBSR_003", "PS_BBSR_004", "PS_PURI_001"],
        "expected_relationships": [
            "SIMILAR_MO",
            "SHARED_PERSON",
            "TEMPORAL_PROXIMITY",
            "CROSS_STATION_LINKAGE"
        ],
    },
    "CLUSTER_C_FRAUD_NETWORK": {
        "cluster_id": "CLUSTER_C_FRAUD_NETWORK",
        "description": "Online stock investment and trading fraud operating across Bhubaneswar and Sambalpur",
        "station_ids": ["PS_BBSR_002", "PS_SBP_001"],
        "expected_relationships": [
            "SHARED_PHONE",
            "SHARED_PERSON",
            "SIMILAR_MO",
            "CROSS_STATION_LINKAGE"
        ],
    },
}
