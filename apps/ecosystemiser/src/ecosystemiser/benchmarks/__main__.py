from hive_logging import get_logger

logger = get_logger(__name__)

"""Main entry point for benchmarking module."""

from ecosystemiser.benchmarks.run_benchmarks import main

if __name__ == "__main__":
    main()
