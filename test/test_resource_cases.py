import json
import shutil
import traceback
from datetime import datetime
from pathlib import Path

from mv_compiler.api import compile, execute

TEST_ROOT = Path(__file__).resolve().parent
RESOURCES_ROOT = TEST_ROOT / "resources"
COMPILED_DIR_NAME = "compiled"
TEST_CONFIG_FILE_NAME = "test.json"
METADATA_FILE_NAME = "metadata.json"

def test_transpilation_and_execution(input_dir: Path):
    """
    Each test case will run the transpiler and execute the generated code,
    then compare the output with the expected output.

    The "input_dir" argument is dynamically provided by conftest.py.
    """
    # --- 1. Arrange ---
    # TEST_* ディレクトリを1ケースとして扱い、入力・出力・期待値・追加設定を集める。
    case_dir = input_dir
    input_dir = case_dir / "sources"
    output_dir = case_dir / COMPILED_DIR_NAME
    expected_output_file = case_dir / "outputs" / "output.txt"
    config = _load_test_config(case_dir)
    metadata = _initial_metadata(case_dir, input_dir, output_dir, config)

    assert expected_output_file.exists(), f"Expected output file not found: {expected_output_file}"

    expected_output = expected_output_file.read_text(encoding="utf-8")
    _prepare_output_dir(output_dir)

    # --- 2. Act ---
    # まずコンパイルする。test.json に expect_compile_error があるケースは、
    # ここで期待したエラー文字列を含む例外が出ればテスト成功として終了する。
    try:
        compile_kwargs = {}
        if strategy := config.get("version_selection_strategy"):
            compile_kwargs["version_selection_strategy"] = strategy

        compile(input_dir, output_dir, **compile_kwargs)
        metadata["compile"] = {"success": True}
    except Exception as exc:
        metadata["compile"] = _error_metadata(exc)
        metadata["completed_at"] = _now()
        _write_metadata(output_dir, metadata)

        expected_error = config.get("expect_compile_error")
        if expected_error and expected_error in str(exc):
            return
        raise

    # エラーを期待していたのにコンパイルが通った場合は、明示的に失敗させる。
    if expected_error := config.get("expect_compile_error"):
        metadata["completed_at"] = _now()
        _write_metadata(output_dir, metadata)
        raise AssertionError(f"Expected compile error containing {expected_error!r}, but compilation succeeded.")

    # コンパイル成功が期待される通常ケースだけ、生成された main.py を実行する。
    try:
        actual_output = execute("main.py", output_dir)
        metadata["execute"] = {"success": True}
        metadata["actual_output"] = actual_output
    except Exception as exc:
        metadata["execute"] = _error_metadata(exc)
        metadata["completed_at"] = _now()
        _write_metadata(output_dir, metadata)
        raise

    metadata["completed_at"] = _now()
    _write_metadata(output_dir, metadata)

    # --- 3. Assert ---
    # 標準出力を期待値と比較する。改行コード差はテスト結果に影響させない。
    assert expected_output.strip().replace('\r\n', '\n') == actual_output.strip().replace('\r\n', '\n'), "Runtime output does not match expected output."

def _load_test_config(case_dir: Path) -> dict:
    config_file = case_dir / TEST_CONFIG_FILE_NAME
    if not config_file.exists():
        return {}
    return json.loads(config_file.read_text(encoding="utf-8"))

def _prepare_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True)

def _initial_metadata(case_dir: Path, input_dir: Path, output_dir: Path, config: dict) -> dict:
    return {
        "case": str(case_dir.relative_to(RESOURCES_ROOT)),
        "input_dir": str(input_dir.relative_to(RESOURCES_ROOT)),
        "output_dir": str(output_dir.relative_to(RESOURCES_ROOT)),
        "config": config,
        "started_at": _now(),
    }

def _error_metadata(exc: Exception) -> dict:
    return {
        "success": False,
        "type": type(exc).__name__,
        "message": str(exc),
        "traceback": traceback.format_exc(),
    }

def _write_metadata(output_dir: Path, metadata: dict) -> None:
    (output_dir / METADATA_FILE_NAME).write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

def _now() -> str:
    return datetime.now().astimezone().isoformat()
