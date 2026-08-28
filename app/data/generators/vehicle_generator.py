import random
from typing import List
from app.models.vehicle import Vehicle

ODISHA_RTO_CODES = ["OD02", "OD05", "OD14", "OD15", "OD09", "OD33", "OD07"]
MAKES_MODELS = [
    ("Mahindra", "Scorpio"),
    ("Mahindra", "Bolero"),
    ("Hero", "Splendor Plus"),
    ("Honda", "Activa 6G"),
    ("TVS", "Apache RTR"),
    ("Maruti", "Swift Desire"),
    ("Hyundai", "Creta"),
    ("Bajaj", "Pulsar 150"),
    ("Royal Enfield", "Classic 350"),
]


def generate_synthetic_vehicles(rng: random.Random, count: int = 140) -> List[Vehicle]:
    """Generates synthetic vehicle records with Odisha registration formats."""
    vehicles: List[Vehicle] = []
    used_regs = set()

    for i in range(count):
        rto = rng.choice(ODISHA_RTO_CODES)
        series = rng.choice(["A", "B", "C", "D", "E", "F", "G", "H", "K", "L", "M", "N"])
        num = rng.randint(1000, 9999)
        reg = f"{rto}{series}{num}"

        while reg in used_regs:
            num = rng.randint(1000, 9999)
            reg = f"{rto}{series}{num}"
        used_regs.add(reg)

        make, model = rng.choice(MAKES_MODELS)
        vtype = "MOTORCYCLE" if "Activa" in model or "Splendor" in model or "Pulsar" in model or "Apache" in model or "Classic" in model else ("SUV" if "Scorpio" in model or "Bolero" in model or "Creta" in model else "SEDAN")

        v = Vehicle(
            registration_number=reg,
            vehicle_type=vtype,
            make=make,
            model=model,
        )
        vehicles.append(v)

    return vehicles
