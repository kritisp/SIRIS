import random
from datetime import date
from typing import List, Tuple
from app.models.person import Person

FIRST_NAMES_MALE = [
    "Rahul", "Vikram", "Soumya", "Debasis", "Pritam", "Rakesh", "Amit", "Subhash", "Tapan", "Manas",
    "Deepak", "Sanjay", "Alok", "Chittaranjan", "Biplab", "Satyabrata", "Ashok", "Gopal", "Suraj", "Sunil",
    "Rajesh", "Santosh", "Biswajit", "Pradeep", "Jitendra", "Manoj", "Dinesh", "Kishore"
]

FIRST_NAMES_FEMALE = [
    "Priyanka", "Sunita", "Swati", "Rashmi", "Manasi", "Anusuya", "Lipsa", "Meenakshi", "Pooja", "Sujata",
    "Anita", "Archana", "Kavita", "Sangita", "Subhashree"
]

LAST_NAMES = [
    "Kumar", "Singh", "Mohanty", "Patnaik", "Sahoo", "Das", "Rout", "Behera", "Nayak", "Panda",
    "Swain", "Pradhan", "Mishra", "Tripathy", "Sethy", "Jena", "Samal", "Parida", "Mahapatra"
]

ALIASES = ["Raju", "Bulu", "Kalia", "Chhota", "Pintu", "Bapu", "Guddu", "Litu", "Muna"]


def generate_synthetic_persons(rng: random.Random, count: int = 220) -> Tuple[List[Person], List[Tuple[Person, str]]]:
    """Generates master person records, alias/name variations, and decoy records."""
    persons: List[Person] = []
    name_variations: List[Tuple[Person, str]] = []

    for i in range(count):
        gender = "MALE" if rng.random() > 0.3 else "FEMALE"
        first = rng.choice(FIRST_NAMES_MALE if gender == "MALE" else FIRST_NAMES_FEMALE)
        last = rng.choice(LAST_NAMES)
        full_name = f"{first} {last}"

        # Missing DOB (~12%) and missing address (~15%) for realistic incomplete records
        dob = date(rng.randint(1975, 2004), rng.randint(1, 12), rng.randint(1, 28)) if rng.random() > 0.12 else None
        addr = f"Plot {rng.randint(1, 600)}, Lane {rng.randint(1, 25)}, Odisha" if rng.random() > 0.15 else None

        p = Person(
            name=full_name,
            date_of_birth=dob,
            gender=gender,
            address=addr,
            identifier_hash=f"hash_person_{i+1:04d}"
        )
        persons.append(p)

        # Generate deliberate representation variations for entity resolution testing
        if i % 6 == 0:
            var_name = f"{first[0]}. {last}"  # e.g., "R. Kumar"
            name_variations.append((p, var_name))
        elif i % 9 == 0:
            var_name = f"{first} {last[0]}."  # e.g., "Rahul K."
            name_variations.append((p, var_name))
        elif i % 14 == 0:
            alias = rng.choice(ALIASES)
            var_name = f"{first} {last} alias {alias}"  # e.g., "Rahul Kumar alias Raju"
            name_variations.append((p, var_name))

    # Add common name decoys (distinct master records sharing exact identical names)
    common_decoys = [
        ("Rahul Kumar", "MALE", date(1988, 5, 14), "Plot 102, Saheed Nagar, Bhubaneswar"),
        ("Rahul Kumar", "MALE", date(1995, 11, 22), "At/PO Cuttack Sadar, Cuttack"),
        ("Sanjay Sahoo", "MALE", date(1982, 3, 10), "Badambadi, Cuttack"),
        ("Sanjay Sahoo", "MALE", date(1991, 8, 19), "Main Road, Sambalpur"),
    ]

    for d_name, d_gender, d_dob, d_addr in common_decoys:
        d_person = Person(
            name=d_name,
            date_of_birth=d_dob,
            gender=d_gender,
            address=d_addr,
            identifier_hash=f"hash_decoy_{rng.randint(1000, 9999)}"
        )
        persons.append(d_person)

    return persons, name_variations
