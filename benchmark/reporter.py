import csv
import re
from pathlib import Path
from typing import Dict

from config import OutputConfig


def _import_matplotlib():
    import matplotlib.pyplot as plt
    return plt


def report_results_switch(csv_path: Path):
    """
    CSV columns:
      name, continuity_switch_count, latest_switch_count, performance_factor
    """
    csv_path = Path(csv_path)

    rows = []
    with csv_path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        required = {"name", "continuity_switch_count", "latest_switch_count", "performance_factor"}
        if reader.fieldnames is None or not required.issubset(set(reader.fieldnames)):
            raise ValueError(f"CSV must have columns: {sorted(required)}; got: {reader.fieldnames}")

        for r in reader:
            name = r["name"]
            c = float(r["continuity_switch_count"])
            l = float(r["latest_switch_count"])
            ratio = (l / c) if c != 0 else (float("inf") if l > 0 else 1.0)
            rows.append((name, c, l, ratio))

    rows.sort(key=lambda t: (t[3], t[2]), reverse=True)
    if not rows:
        return

    names = [t[0] for t in rows]
    cont = [t[1] for t in rows]
    latest = [t[2] for t in rows]
    ratio = [t[3] for t in rows]
    x = list(range(len(names)))

    plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(16, 6))

    # Bars: ratio (no legend entry)
    ax.bar(
        x,
        ratio,
        edgecolor="black",
        facecolor="white",
        hatch="///",
        linewidth=1.0,
    )

    # Red reference line at 1.0 (no legend entry)
    ax.axhline(y=1.0, color="red", linestyle="-", linewidth=1.5)

    ax.set_xlabel("Benchmarks", fontsize=18)
    ax.set_ylabel("Switch-count ratio\n(Latest / Continuity) (×)", fontsize=18)

    ax.set_xticks(x)
    ax.set_xticklabels(names, rotation=45, ha="right")

    ax.tick_params(axis="x", labelsize=18)
    ax.tick_params(axis="y", labelsize=18)
    ax.grid(axis="y", linestyle="--", alpha=0.7)

    # Right axis: counts (log)
    axr = ax.twinx()
    axr.set_yscale("log")
    axr.set_ylabel("Switch count (log scale)", fontsize=18)
    axr.tick_params(axis="y", labelsize=18)

    # Lines: switch counts (legend kept)
    line1, = axr.plot(
        x, cont,
        marker="o", linestyle="-", linewidth=1.2, color="black",
        label="continuity-first",
    )
    line2, = axr.plot(
        x, latest,
        marker="s", linestyle="--", linewidth=1.2, color="black",
        label="latest-first",
    )

    # Legend: top-right, right-aligned
    leg = ax.legend(
        handles=[line1, line2],
        loc="upper right",
        fontsize=16,
        frameon=True,
        alignment="right",   # matplotlib>=3.6 くらいで効く。古いと無視されるが害はない
    )
    # 右詰めが効かない環境向けの保険（Textオブジェクトを右寄せ）
    for t in leg.get_texts():
        t.set_ha("right")

    plt.tight_layout()

    output_pdf = csv_path.parent / "switch_ratio_results.pdf"
    plt.savefig(output_pdf, format="pdf")
    plt.show()
    return output_pdf

def report_results(csv_path: Path, config: OutputConfig):
    """Reads the CSV results and outputs them with the specified format."""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        results = [row for row in reader]

    mode = getattr(config, 'mode', 'suite')
    _report_to_cli(results, mode)

    if config.format == 'graph':
        if mode == 'gradual':
            _report_to_gradual_line_graph(results, csv_path)
        elif mode == 'perf_overhead':
            _report_to_perf_overhead_bar_graph(results, csv_path)
        else:
            _report_to_suite_bar_graph(results, csv_path)

def _report_to_suite_bar_graph(results: list[Dict], csv_path: Path):

    # 1. データを準備し、パフォーマンス倍率を計算
    valid_results = []
    for r in results:
        t_time = float(r['transpiled_time'])
        v_time = float(r['vanilla_time'])
        if t_time > 0 and v_time > 0:
            # 'performance_factor' (何倍遅いか) を計算して、辞書に追加
            r['performance_factor'] = t_time / v_time
            valid_results.append(r)
        
    # パフォーマンス倍率で降順にソート
    sorted_results = sorted(valid_results, key=lambda r: r['performance_factor'], reverse=True)

    if not sorted_results:
        return

    # グラフ描画用にデータを抽出
    target_names = [r['name'] for r in sorted_results]
    factors = [r['performance_factor'] for r in sorted_results]

    # 2. グラフを描画
    plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 6))
    
    ax.bar(target_names, factors, color='white', edgecolor='black', hatch='xx', linewidth=1.0)
    

    # ax.set_title('MVO Compiler Performance Factor vs. Vanilla Python')
    ax.set_xlabel('Benchmarks', fontsize=18)
    ax.set_ylabel('Average execution time\nrelative to Python', fontsize=18)
    ax.grid(axis='y', linestyle='--', alpha=0.7)

    ax.tick_params(axis='x', labelsize=18)
    ax.tick_params(axis='y', labelsize=18)

    # Y軸の基準線を 1.0 (vanillaと同じ速さ) に引く
    ax.axhline(y=1.0, color='black', linestyle='--', linewidth=1.2)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # 3. グラフをファイルに保存
    output_path = csv_path.parent / "benchmark_results.pdf"
    plt.savefig(output_path, format="pdf")
    plt.show()

def _report_to_gradual_line_graph(results: list[Dict], csv_path: Path):
    """「段階的オーバーヘッド」モードの結果を折れ線グラフとして保存する。"""
    
    # 1. データを準備し、ターゲット名から横軸の「数値」を抽出
    plot_data = []
    for r in results:
        t_time = float(r['transpiled_time'])
        v_time = float(r['vanilla_time'])
        if t_time > 0 and v_time > 0:
            # ターゲット名の末尾から数値を抽出 (例: "fib20_10000" -> 10000)
            match = re.search(r'_(\d+)$', r['name'])
            if match:
                x_value = int(match.group(1))
                y_value = t_time / v_time
                plot_data.append({'x': x_value, 'y': y_value})
            
    # 2. 横軸の数値で、昇順にソート
    sorted_data = sorted(plot_data, key=lambda d: d['x'])

    if not sorted_data:
        return

    # 3. グラフ描画用にX軸とY軸のデータを抽出
    x_values = [d['x'] for d in sorted_data]
    y_values = [d['y'] for d in sorted_data]
    # 2. 折れ線グラフを描画
    plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 6))
    # X軸とY軸に、カテゴリ名ではなく、数値のリストを渡す
    ax.plot(x_values, y_values, marker='o', linestyle='-', color='dodgerblue')
    
    # ax.set_title('Performance Factor vs. Benchmark Parameter')
    ax.set_xlabel('Number of Fallbacks (out of ~70k)', fontsize=18) # X軸のラベルを汎用的に
    ax.set_ylabel('Average execution time\nrelative to Python', fontsize=18)

    ax.tick_params(axis='x', labelsize=18)
    ax.tick_params(axis='y', labelsize=18)
    ax.grid(True, linestyle='--', alpha=0.7)
    ax.axhline(y=1.0, color='black', linestyle='--', linewidth=1.2)


    plt.tight_layout()

    # 3. グラフをファイルに保存
    output_path = csv_path.parent / "gradual_overhead_results.pdf"
    plt.savefig(output_path, format="pdf")
    plt.show()

def _report_to_perf_overhead_bar_graph(results: list[Dict], csv_path: Path):
    def _is_composed_benchmark(name: str) -> bool:
        # Keep backward compatibility: old target name was "application".
        normalized = re.sub(r"[\s_-]+", "", name).lower()
        return normalized in {"composed", "application"}

    # 1. データを準備し、スループット倍率を計算
    valid_results = []
    for r in results:
        t_time = float(r['transpiled_time'])
        v_time = float(r['vanilla_time'])
        if t_time > 0 and v_time > 0:
            # 'throughput_ratio' (Python を 1.0 としたスループット倍率)
            r['throughput_ratio'] = v_time / t_time
            valid_results.append(r)

    # 通常はスループット倍率で昇順（遅い順）。Composed/Applicationは常に右端に配置。
    sorted_results = sorted(
        valid_results,
        key=lambda r: (_is_composed_benchmark(r['name']), r['throughput_ratio'])
    )

    if not sorted_results:
        return

    # グラフ描画用にデータを抽出
    target_names = [r['name'] for r in sorted_results]
    ratios = [r['throughput_ratio'] for r in sorted_results]
    bar_colors = [
        '#f2f2f2' if not _is_composed_benchmark(name) else '#f4a261'
        for name in target_names
    ]

    # 2. グラフを描画
    plt = _import_matplotlib()
    fig, ax = plt.subplots(figsize=(10, 6))

    ax.bar(target_names, ratios, color=bar_colors, edgecolor='black', hatch='xx', linewidth=1.0)

    ax.set_xlabel('Benchmarks', fontsize=18)
    ax.set_ylabel('Average throughput\nrelative to vanilla Python', fontsize=18)
    ax.tick_params(axis='x', labelsize=18)
    ax.tick_params(axis='y', labelsize=18)

    # Y軸の目盛りは 0.0〜1.0 を 0.2 刻みで固定（表示ラベル）
    tick_values = [0.0, 0.2, 0.4, 0.6, 0.8, 1.0]
    ax.set_yticks(tick_values)
    ax.set_yticklabels(['0'] + [f"{v:.1f}" for v in tick_values[1:]])
    ax.set_ylim(bottom=0.0)

    # 0.1 刻みの補助目盛りを追加（ラベルなし）
    minor_ticks = [i / 10 for i in range(1, 10) if i % 2 == 1]
    ax.set_yticks(minor_ticks, minor=True)

    # 主要・補助の水平線
    ax.grid(which='major', axis='y', linestyle='-', alpha=0.25, linewidth=0.8)
    ax.grid(which='minor', axis='y', linestyle='-', alpha=0.12, linewidth=0.6)

    # Y軸の基準線を 1.0 (vanillaと同じスループット) に引く
    ax.axhline(y=1.0, color='black', linestyle='--', linewidth=1.2)

    plt.xticks(rotation=45, ha='right')
    plt.tight_layout()

    # 3. グラフをファイルに保存
    output_path = csv_path.parent / "perf_overhead_results.pdf"
    plt.savefig(output_path, format="pdf")
    plt.show()

def _report_to_cli(results: list[Dict], mode: str):
    """ベンチマーク結果をCLIに表示する。"""
    print("\n\n--- Benchmark Summary ---")
    for i, result in enumerate(results):
        name = result['name']
        t_time = float(result['transpiled_time'])
        v_time = float(result['vanilla_time'])

        if i > 0 and mode == 'suite':
            print("")

        print(f"Target: {name}")
        print(f"  Transpiled MVO:   {t_time:.6f} seconds")
        print(f"  Vanilla Python:   {v_time:.6f} seconds")

        if t_time > 0 and v_time > 0:
            if mode == 'perf_overhead':
                throughput_ratio = v_time / t_time
                print(f"  Throughput: {throughput_ratio:.2f}x of Python")
            else:
                performance_factor = t_time / v_time
                print(f"  Factor: {performance_factor:.2f}x slower")
