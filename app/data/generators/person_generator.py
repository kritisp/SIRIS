import random
from datetime import date
from typing import List, Tuple
from app.models.person import Person

FIRST_NAMES_MALE = [
    "Rahul", "Vikram", "Soumya", "Debasis", "Pritam", "Rakesh", "Amit", "Subhash", "Tapan", "Manas",
    "Deepak", "Sanjay", "Alok", "Chittaranjan", "Biplab", "Satyabrata", "Ashok", "Gopal", "Suraj", "Sunil"
]

FIRST_NAMES_FEMALE = [
    "Priyanka", "Sunita", "Swati", "Rashmi", "Manasi", "Anusuya", "Lipsa", "Meenakshi", "Pooja", "Sujata"
]

LAST_NAMES = [
    "Kumar", "Singh", "Mohanty", "Patnaik", "Sahoo", "Das", "Rout", "Behera", "Nayak", "Panda",
    "Swain", "Pradhan", "Mishra", "Tripathy", "Sethy", "Jena", "Samal", "Parida"
]


def generate_synthetic_persons(rng: random.Random, count: int = 200) -> Tuple[List[Person], List[Tuple[Person, str]]]:
    """Generates synthetic person records, name variation aliases, and decoy records."""
    persons: List[Person] = []
    variations: List[Tuple[Person, str]] = []

    for i in range(count):
        gender = "MALE" if rng.random() > 0.3 else "FEMALE"
        first = rng.choice(FIRST_NAMES_MALE if gender == "MALE" else FIRST_NAMES_FEMALE)
        last = rng.choice(LAST_NAMES)
        full_name = f"{first} {last}"

        # 10% chance DOB is missing for realistic data quality
        dob = date(rng.randint(1975, 2004), rng.randint(1, 12), rng.randint(1, 28)) if rng.random() > 0.1 else None
        
        # 15% chance address is missing/incomplete
        addr = f"Plot {rng.randint(1, 500)}, Colony {rng.randint(1, 12)}, Bhubaneswar, Odisha" if rng.random() > 0.15 else None
        
        p = Person(
            name=full_name,
            date_of_birth=dob,
            gender=gender,
            address=addr,
            identifier_hash=f"hash_person_{i+1:04d}"
        )
        persons.append(p)

        # Create name variations for planted entity resolution testing
        if i % 8 == 0:
            var_name = f"{first[0]}. {last}"  # e.g., "R. Kumar"
            variations.append((p, var_name))
        elif i % 12 == 0:
            var_name = f"{first} {last[0]}."  # e.g., "Rahul K."
            variations.append((p, var_name))

    return persons, variations
