import random
from typing import List
from app.models.location import Location

# Anchor coordinates for key Odisha hubs
ANCHOR_LOCATIONS = [
    {"city": "Bhubaneswar", "locality": "Janpath Road, Master Canteen", "district": "Khordha (Bhubaneswar)", "state": "Odisha", "lat": 20.2662, "lng": 85.8398},
    {"city": "Bhubaneswar", "locality": "Patia College Square", "district": "Khordha (Bhubaneswar)", "state": "Odisha", "lat": 20.3533, "lng": 85.8188},
    {"city": "Bhubaneswar", "locality": "Rasulgarh Square", "district": "Khordha (Bhubaneswar)", "state": "Odisha", "lat": 20.2980, "lng": 85.8620},
    {"city": "Bhubaneswar", "locality": "Khandagiri Square", "district": "Khordha (Bhubaneswar)", "state": "Odisha", "lat": 20.2580, "lng": 85.7870},
    {"city": "Cuttack", "locality": "Badambadi Bus Stand", "district": "Cuttack", "state": "Odisha", "lat": 20.4530, "lng": 85.8790},
    {"city": "Cuttack", "locality": "Chandi Mandir Chhak", "district": "Cuttack", "state": "Odisha", "lat": 20.4680, "lng": 85.8650},
    {"city": "Puri", "locality": "Grand Road, Bada Danda", "district": "Puri", "state": "Odisha", "lat": 19.8048, "lng": 85.8179},
    {"city": "Puri", "locality": "Swargadwar Beach Front", "district": "Puri", "state": "Odisha", "lat": 19.7950, "lng": 85.8230},
    {"city": "Sambalpur", "locality": "VSS Marg, Laxmi Talkies Square", "district": "Sambalpur", "state": "Odisha", "lat": 21.4669, "lng": 83.9756},
    {"city": "Rourkela", "locality": "Main Road, Sector 5", "district": "Sundargarh", "state": "Odisha", "lat": 22.2257, "lng": 84.8536},
]


def generate_synthetic_locations(rng: random.Random, count: int = 100) -> List[Location]:
    """Generates synthetic location records clustered around major Odisha hubs."""
    locations: List[Location] = []

    # 1. First add exact anchor locations
    for anchor in ANCHOR_LOCATIONS:
        loc = Location(
            address=f"{anchor['locality']}, Near Landmark, {anchor['city']}",
            locality=anchor["locality"],
            city=anchor["city"],
            district=anchor["district"],
            state=anchor["state"],
            latitude=anchor["lat"],
            longitude=anchor["lng"],
        )
        locations.append(loc)

    # 2. Fill remaining with perturbed nearby coordinates (within ~500m to 3km radius)
    needed = max(0, count - len(locations))
    for i in range(needed):
        anchor = rng.choice(ANCHOR_LOCATIONS)
        # Lat/lng offset jitter (~0.005 approx 550 meters)
        lat_jitter = rng.uniform(-0.015, 0.015)
        lng_jitter = rng.uniform(-0.015, 0.015)
        loc = Location(
            address=f"Plot No. {rng.randint(10, 999)}, Lane {rng.randint(1, 20)}, {anchor['locality']}, {anchor['city']}",
            locality=anchor["locality"],
            city=anchor["city"],
            district=anchor["district"],
            state=anchor["state"],
            latitude=round(anchor["lat"] + lat_jitter, 6),
            longitude=round(anchor["lng"] + lng_jitter, 6),
        )
        locations.append(loc)

    return locations
