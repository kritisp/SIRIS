import logging
import sys
from pathlib import Path

# Add project root directory to python path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.seeds.neo4j_realistic_datasets import neo4j_realistic_datasets

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("clear_neo4j_test_data")


def main():
    logger.info("Clearing all synthetic test data tagged with environment='siris-test' from Neo4j...")
    neo4j_realistic_datasets.clear_all_test_data()
    logger.info("Neo4j synthetic test data successfully cleared.")


if __name__ == "__main__":
    main()
