import shutil
from pathlib import Path

from bench_constants import (
    LOOP_PLACEHOLDER,
    MODE_DIR_MAP,
    MVO_DIR_NAME,
    SWITCH_LOOP_COUNT,
    STRATEGY_CONTINUITY,
    TRANSPILED_DIR_NAME,
    VANILLA_DIR_NAME,
)
from bench_log import log
from bench_paths import TARGETS_ROOT, ensure_project_root_on_path
from config import BenchmarkConfig

ensure_project_root_on_path()

from src.mvo_compiler.mvo_compiler import compile

def _generate_script_from_template(template_path: Path, output_path: Path, loop_count: int):
    """
    Generate an executable Python script from a template.
    """
    template_str = template_path.read_text(encoding='utf-8')
    script_str = template_str.replace(LOOP_PLACEHOLDER, str(loop_count))
    output_path.write_text(script_str, encoding='utf-8')

def prepare_target(target_name: str, result_dir: Path, config: BenchmarkConfig, compile_strategy: str = STRATEGY_CONTINUITY) -> bool:
    """
    Prepare the specified benchmark target.
    """
    log(f"Preparing files: target={target_name}, mode={config.mode}, strategy={compile_strategy}")
    base_path = TARGETS_ROOT / MODE_DIR_MAP[config.mode]

    target_path = base_path / target_name

    if config.mode in ('gradual', 'suite', 'perf_overhead'):
        mvo_source_path = target_path / MVO_DIR_NAME
        vanilla_source_path = target_path / VANILLA_DIR_NAME

        if not mvo_source_path.is_dir() or not vanilla_source_path.is_dir():
            log(f"Error: Benchmark target '{target_name}' is incomplete.")
            return False

        transpiled_run_path = result_dir / TRANSPILED_DIR_NAME
        vanilla_run_path = result_dir / VANILLA_DIR_NAME
        transpiled_run_path.mkdir(parents=True)
        vanilla_run_path.mkdir(parents=True)
        
        # 1. Transpile & Copy
        compile(mvo_source_path, transpiled_run_path)
        shutil.copytree(vanilla_source_path, vanilla_run_path, dirs_exist_ok=True)
        
        # 2. Generate Scripts from templates
        log(f"  Generate templates (loop={config.loop_count})")
        _generate_script_from_template(
            transpiled_run_path / "main.py", 
            transpiled_run_path / "main.py", 
            config.loop_count
        )
        _generate_script_from_template(
            vanilla_source_path / "main.py", 
            vanilla_run_path / "main.py",
            config.loop_count
        )
    else:
        mvo_source_path = target_path
        transpiled_run_path = result_dir
        compile(mvo_source_path, transpiled_run_path, version_selection_strategy=compile_strategy)
        _generate_script_from_template(
            transpiled_run_path / "main.py", 
            transpiled_run_path / "main.py", 
            SWITCH_LOOP_COUNT
        )
    return True
