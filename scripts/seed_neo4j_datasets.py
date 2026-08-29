import sys
import argparse
import logging
from pathlib import Path

# Add project root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.seeds.neo4j_realistic_datasets import neo4j_realistic_datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("seed_neo4j_datasets")


def main():
    parser = argparse.ArgumentParser(description="Seed realistic synthetic test datasets into Neo4j for S.I.R.I.S.")
    parser.add_argument(
        "--dataset",
        type=str,
        default="all",
        help="Dataset key to seed (e.g. 1_simple_direct, 10_complex_multistation, or 'all')",
    )
    args = parser.parse_args()

    if args.dataset == "all":
        logger.info("Seeding ALL 10 realistic synthetic test datasets into Neo4j...")
        results = neo4j_realistic_datasets.seed_all()
        for k, v in results.items():
            logger.info(f"Seeded dataset [{k}] -> {len(v['cases'])} cases.")
        logger.info("All datasets successfully seeded into Neo4j.")
    else:
        logger.info(f"Seeding dataset [{args.dataset}] into Neo4j...")
        v = neo4j_realistic_datasets.seed_dataset(args.dataset)
        logger.info(f"Seeded dataset [{args.dataset}] -> {len(v['cases'])} cases successfully.")


if __name__ == "__main__":
    main()
