import random
from typing import List
from app.models.phone import Phone

PHONE_PREFIXES = ["9861", "9437", "7008", "9937", "8249", "9178", "7978", "8895"]


def generate_synthetic_phones(rng: random.Random, count: int = 180) -> List[Phone]:
    """Generates synthetic Indian phone records with normalized E.164 formats."""
    phones: List[Phone] = []
    used_numbers = set()

    for i in range(count):
        prefix = rng.choice(PHONE_PREFIXES)
        suffix = rng.randint(105000, 999999)
        num = f"+91{prefix}{suffix}"

        while num in used_numbers:
            suffix = rng.randint(105000, 999999)
            num = f"+91{prefix}{suffix}"
        used_numbers.add(num)

        p = Phone(
            normalized_number=num,
            number_hash=f"hash_phone_{i+1:04d}"
        )
        phones.append(p)

    return phones
