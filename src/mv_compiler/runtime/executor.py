import os
import subprocess
import sys
from pathlib import Path

from ..compiler.common.util import logger


def execute_generated(entry_file: str, dir: Path) -> str:
    """
    生成されたエントリファイルを実行する。
    """
    logger.debug_log("\n--- Running Generated Code ---")
    entry_file_path = dir / entry_file
    try:
        env = os.environ.copy()
        env["PYTHONPATH"] = str(dir.resolve())

        result = subprocess.run(
            [sys.executable, str(entry_file_path.resolve())],
            capture_output=True,
            text=True,
            check=True,
            env=env,
        )
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error_log("Execution failed:")
        raise RuntimeError(f"Execution failed for {entry_file_path}: {e.stderr}")
