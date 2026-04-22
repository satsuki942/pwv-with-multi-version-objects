import argparse
from pathlib import Path

from mv_compiler.api import compile, execute
from mv_compiler.compiler.common.util import logger
from mv_compiler.compiler.common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY, VERSION_SELECTION_STRATEGIES

INPUT_BASE_PATH = Path(".")
OUTPUT_BASE_PATH = Path("output")
ENTRY_FILE_NAME = "main.py"

def main():
    parser = argparse.ArgumentParser(description="Compile and Run MVO Test Cases.")
    parser.add_argument("target_dir", help="Path to the test case directory (e.g., simple_cases/01).")
    parser.add_argument(
        "--strategy",
        choices=list(VERSION_SELECTION_STRATEGIES),
        default=DEFAULT_VERSION_SELECTION_STRATEGY,
        help="Version selection strategy (default: continuity).",
    )
    parser.add_argument("--debug", action="store_true", help="Enable debug logging.")
    
    args = parser.parse_args()

    if args.debug:
        logger.DEBUG_MODE = True
        logger.debug_log("Debug mode enabled.")
    
    compile(
        input_dir=INPUT_BASE_PATH / args.target_dir,
        output_dir=OUTPUT_BASE_PATH,
        version_selection_strategy=args.strategy,
        delete_output_dir=True
    )
    output = execute(
        entry_file=ENTRY_FILE_NAME,
        dir=OUTPUT_BASE_PATH
    )
    logger.log(output)

if __name__ == "__main__":
    main()
