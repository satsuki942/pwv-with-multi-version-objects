from pathlib import Path

from mv_compiler.api import compile, execute

TEST_ROOT = Path(__file__).resolve().parent
RESOURCES_ROOT = TEST_ROOT / "resources"

def test_transpilation_and_execution(input_dir: Path, tmp_path: Path):
    """
    Each test case will run the transpiler and execute the generated code,
    then compare the output with the expected output.

    The "input_dir" argument is dynamically provided by conftest.py.
    """
    # --- 1. Arrange ---
    input_dir = input_dir / "sources"
    expected_output_file = input_dir.parent / "outputs" / "output.txt"
    assert expected_output_file.exists(), f"Expected output file not found: {expected_output_file}"
        
    expected_output = expected_output_file.read_text(encoding="utf-8")

    # --- 2. Act ---
    compile(input_dir, tmp_path)
    actual_output = execute("main.py", tmp_path)

    # --- 3. Assert ---
    assert expected_output.strip().replace('\r\n', '\n') == actual_output.strip().replace('\r\n', '\n'), "Runtime output does not match expected output."
