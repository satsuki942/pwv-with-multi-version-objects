import csv
from datetime import datetime
from pathlib import Path
from typing import List, Dict

from bench_constants import MODE_DIR_MAP, RESULTS_CSV_NAME, STRATEGY_CONTINUITY, STRATEGY_LATEST
from bench_log import log
from bench_paths import RESULTS_ROOT, TARGETS_ROOT
from config import BenchmarkConfig
from preparer import prepare_target
from executor import execute_and_measure, execute_and_measure_for_switch_count


def _resolve_targets(bench_config: BenchmarkConfig) -> list[str]:
    targets_path = TARGETS_ROOT / MODE_DIR_MAP[bench_config.mode]
    if bench_config.mode in ('suite', 'perf_overhead') and bench_config.target_name:
        target_dir = targets_path / bench_config.target_name
        if not target_dir.is_dir():
            log(f"Target not found: {target_dir}")
            return []
        return [bench_config.target_name]

    if not targets_path.is_dir():
        log(f"Targets directory not found: {targets_path}")
        return []

    return sorted([d.name for d in targets_path.iterdir() if d.is_dir()])

def run_benchmarks(bench_config: BenchmarkConfig) -> Path | None:
    """
    設定に基づき、適切なベンチマークターゲット群に対して、
    準備・測定のパイプラインを実行し、結果をCSVに保存する。
    """
    # 1. 結果保存用ディレクトリの準備
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    result_dir = RESULTS_ROOT / timestamp
    result_dir.mkdir(parents=True)
    log(f"Results directory: {result_dir}")
    
    results_data: List[Dict] = []

    # 2. モードに応じて実行対象ターゲットを決定
    targets_to_run = _resolve_targets(bench_config)
    log(f"Targets to run ({bench_config.mode}): {', '.join(targets_to_run) if targets_to_run else '(none)'}")

    # 3. 各ターゲットについて「準備」と「測定」を順番に実行
    if bench_config.mode == 'switch':
        for target_name in targets_to_run:
            log(f"---- Target: {target_name} ----")
            log(f"Preparing target: {target_name} (continuity)")
            target_result_dir0 = result_dir / target_name / STRATEGY_CONTINUITY
            target_result_dir1 = result_dir / target_name / STRATEGY_LATEST
            if not prepare_target(target_name, target_result_dir0, bench_config, compile_strategy=STRATEGY_CONTINUITY):
                log(f"Skipped target: {target_name} (continuity)")
                continue
            log(f"Preparing target: {target_name} (latest)")
            if not prepare_target(target_name, target_result_dir1, bench_config, compile_strategy=STRATEGY_LATEST):
                log(f"Skipped target: {target_name} (latest)")
                continue

            log(f"Executing target: {target_name} (switch count)")
            result = execute_and_measure_for_switch_count(target_name, result_dir / target_name, bench_config)
            results_data.append(result)
    else:
        for target_name in targets_to_run:
            log(f"---- Target: {target_name} ----")
            log(f"Preparing target: {target_name}")
            target_result_dir = result_dir / target_name
            
            if not prepare_target(target_name, target_result_dir, bench_config):
                log(f"Skipped target: {target_name}")
                continue
            
            log(f"Executing target: {target_name}")
            result = execute_and_measure(target_name, target_result_dir, bench_config)
            results_data.append(result)
    
    # 4. 総合結果をCSVファイルに保存
    if not results_data:
        return None
        
    csv_path = result_dir / RESULTS_CSV_NAME
    try:
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=results_data[0].keys())
            writer.writeheader()
            writer.writerows(results_data)
        return csv_path
    except (IOError, IndexError) as e:
        return None
