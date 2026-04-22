import pytest

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TEST_ROOT = PROJECT_ROOT / "test"
RESOURCES_ROOT = TEST_ROOT / "resources"
collect_ignore_glob = ["resources/**/sources/*.py"]

def pytest_addoption(parser):
    """Adds the --target_dir command-line option to pytest."""
    parser.addoption(
        "--target_dir", action="store", default="", help="Run tests only on a specific directory"
    )

def pytest_generate_tests(metafunc):
    """
    Dynamically generates test cases based on the --target_dir option.
    This hook is called by pytest during test collection.
    """

    if "input_dir" in metafunc.fixturenames:
        target_path_str = metafunc.config.getoption("--target_dir")
        
        search_root = RESOURCES_ROOT
        if target_path_str:
            candidate = RESOURCES_ROOT / target_path_str
            if not candidate.is_dir():
                parts = Path(target_path_str).parts
                if parts:
                    last = parts[-1]
                    if not last.startswith("TEST_"):
                        parts = parts[:-1] + (f"TEST_{last}",)
                    candidate = RESOURCES_ROOT.joinpath(*parts)
            if candidate.name in {"sources", "outputs"}:
                parent = candidate.parent
                if (parent / "sources").is_dir() and (parent / "outputs").is_dir():
                    candidate = parent
            search_root = candidate

        if not search_root.is_dir():
            pytest.fail(f"Test case directory not found: {search_root}")

        # If the search root itself is a test case, use it directly.
        if (search_root / "sources").is_dir() and (search_root / "outputs").is_dir():
            test_case_dirs = [search_root]
        else:
            # Collect test case directories: resources/**/TEST_*/{sources, outputs}
            test_case_dirs = [
                p for p in search_root.glob("**/TEST_*")
                if p.is_dir()
                and (p / "sources").is_dir()
                and (p / "outputs").is_dir()
            ]
        if not test_case_dirs:
            pytest.fail(f"No test cases (directories with sources/outputs) found in {search_root}")

        # Parametrize the test function with the collected directories
        metafunc.parametrize(
            "input_dir", 
            test_case_dirs, 
            ids=[str(p.relative_to(RESOURCES_ROOT)) for p in test_case_dirs]
        )

DEBUG_MODE = False

def debug_log(message: str):
    """Prints a debug message."""
    if DEBUG_MODE:
        print(f"[LOG]     {message}")

def success_log(message: str):
    """Prints a success message."""
    if DEBUG_MODE:
        print(f"[SUCCESS] {message}")

def error_log(message: str):
    """Prints an error message."""
    print(f"[ERROR]   {message}")

def no_header_log(message: str):
    """Prints a message without a header."""
    print(message)

def log(message: str):
    """Prints a general message that should always be visible."""
    print(message)
