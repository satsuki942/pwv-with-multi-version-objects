import ast
import shutil
from pathlib import Path

from .versioned_source.transformer import has_versioned_source_syntax, transform_versioned_source_module
from .common.util import logger
from .common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY

def compile_project(
    input_dir: Path,
    output_dir: Path,
    *,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
    delete_output_dir: bool = True,
) -> None:
    """
    入力ディレクトリ内のソースをコンパイルし、出力ディレクトリに書き出す。
    """
    # --- 1. 出力ディレクトリのクリーン ---
    if output_dir.exists() and delete_output_dir:
        logger.debug_log(f"Cleaning output directory: {output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # --- 2. ASTの変換 ---
    transformed_files = transform_project(
        input_dir,
        version_selection_strategy=version_selection_strategy,
    )

    # --- 3. 出力ディレクトリへ書き出し ---
    for rel_path, transformed_ast in transformed_files:
        if transformed_ast:
            write_single_file(output_dir, rel_path, transformed_ast)
        else:
            logger.error_log("Something went wrong during transformation; no output generated.")

def transform_project(
    input_dir: Path,
    *,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
) -> list[tuple[Path, ast.AST | None]]:
    """
    入力ディレクトリ内の Python ファイルを versioned source DSL 前提で変換し、ASTを返す。
    """
    out: list[tuple[Path, ast.AST]] = []
    for source_file in sorted(input_dir.glob("**/*.py")):
        if "_mv_mapping" in source_file.parts:
            continue
        rel_path = source_file.relative_to(input_dir)
        source_code = source_file.read_text(encoding="utf-8-sig")
        tree = ast.parse(source_code)

        # DSL を含むモジュールだけ新 compiler に通し、それ以外は通常 Python としてコピーする。
        if has_versioned_source_syntax(tree):
            logger.debug_log(f"Transforming versioned source module: {rel_path}")
            _, transformed_ast = transform_versioned_source_module(
                rel_path,
                tree,
                version_selection_strategy=version_selection_strategy,
            )
            out.append((rel_path, transformed_ast))
        else:
            logger.debug_log(f"Copying normal file: {rel_path}")
            out.append((rel_path, tree))

    return out

def write_single_file(output_dir: Path, original_rel_path: Path, tree: ast.AST) -> None:
    """変換後ASTを指定ディレクトリに1ファイル書き出す。"""
    ast.fix_missing_locations(tree)
    generated_code = ast.unparse(tree)

    output_path = output_dir / original_rel_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(generated_code)

    logger.debug_log(f"Generated: {output_path.resolve()}")
