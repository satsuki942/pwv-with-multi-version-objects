import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "test"
RESOURCES_ROOT = TEST_ROOT / "resources"

# File template for the test case
MAIN_PY_TEMPLATE = """
# このテストケースで検証したい振る舞いをここに書く。
from example import Example


def main():
    obj = Example(10)
    print(obj.value())


if __name__ == "__main__":
    main()
"""

EXAMPLE_V1_TEMPLATE = """
class Example:
    def __init__(self, x: int):
        self.x = x

    def value(self):
        return self.x
"""

EXAMPLE_V2_TEMPLATE = """
class Example:
    def __init__(self, y: int):
        self.y = y

    def value(self):
        return self.y * 2
"""

MODULES_JSON_TEMPLATE = """{
  "modules": {
    "example": {
      "module_path": "example",
      "versions": [1, 2],
      "entity_mappings": [
        {
          "entity_key": "Example",
          "kind": "class",
          "source_names": {
            "1": "Example",
            "2": "Example"
          }
        }
      ]
    }
  }
}
"""

def create_test_case(test_case_path: str):
    """
    Create a new test case structure and its expected ouput at the specified path.
    """

    log(f"--- Creating new test case: {test_case_path} ---")

    # --- 1. Create directories for input and expected output ---
    raw_path = Path(test_case_path)
    if raw_path.name.startswith("TEST_"):
        case_dir = RESOURCES_ROOT / raw_path
    else:
        case_dir = RESOURCES_ROOT / raw_path.parent / f"TEST_{raw_path.name}"

    input_dir = case_dir / "sources"
    expected_file = case_dir / "outputs" / "output.txt"
    expected_parent_dir = expected_file.parent


    if input_dir.exists():
        error_log(f"Test case directory already exists: {input_dir}")
        log("Aborting to prevent overwriting.")
        return
    if expected_file.exists():
        error_log(f"Expected output file already exists: {expected_file}")
        log("Aborting to prevent overwriting.")
        return

    try:
        input_dir.mkdir(parents=True, exist_ok=True)
        expected_parent_dir.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        error_log(f"Failed to create directories: {e}")
        return

    # --- 2. Create source and expected files ---
    mapping_dir = input_dir / "_mv_mapping"
    mapping_dir.mkdir(parents=True, exist_ok=True)

    (input_dir / "main.py").write_text(MAIN_PY_TEMPLATE, encoding="utf-8")
    (input_dir / "example__1__.py").write_text(EXAMPLE_V1_TEMPLATE, encoding="utf-8")
    (input_dir / "example__2__.py").write_text(EXAMPLE_V2_TEMPLATE, encoding="utf-8")
    (mapping_dir / "modules.json").write_text(MODULES_JSON_TEMPLATE, encoding="utf-8")
    expected_file.touch()

    log("\nSuccessfully created test case structure:")
    log(f"  - Input:     {input_dir}")
    log(f"  - Expected:  {expected_file}")
    log("\nPlease edit the generated files to define your test.")

def error_log(message: str):
    """Prints an error message."""
    print(f"[ERROR]   {message}")

def log(message: str):
    """Prints a general message that should always be visible."""
    print(message)

def main():
    """
    Parse command-line arguments and Create the test case structure.
    """
    parser = argparse.ArgumentParser(
        description="Create a new test case structure for the MVO compiler."
    )
    parser.add_argument(
        "test_case_path",
        help="The relative path for the new test case (e.g., 'class/attr/01_basic' or 'module/01_mixed')."
    )
    args = parser.parse_args()
    
    create_test_case(args.test_case_path)

if __name__ == "__main__":
    main()
