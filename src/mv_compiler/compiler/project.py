import ast
import shutil
from pathlib import Path

from .module.compiler import transform_versioned_module
from .scanner import create_project_structure
from .common.util import logger
from .common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY
from .common.util.constants import (
    PROJECT_SYNC_MODULES_KEY,
    PROJECT_INCOMPATIBILITIES_KEY,
    PROJECT_NORMAL_FILES_KEY,
    PROJECT_VERSIONED_MODULES_KEY,
    PROJECT_MODULE_MAPPINGS_KEY,
)

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
    project_structure: dict | None = None,
) -> list[tuple[Path, ast.AST | None]]:
    """
    入力ディレクトリ内の通常ファイルとversioned moduleを変換し、ASTを返す。
    """
    if project_structure is None:
        project_structure = create_project_structure(input_dir)
    logger.success_log(
        f"Found {len(project_structure[PROJECT_SYNC_MODULES_KEY])} sync modules and {len(project_structure[PROJECT_NORMAL_FILES_KEY])} normal files in {input_dir}."
    )
    logger.success_log(f"Completed parsing and classifying files in {input_dir}.")

    out: list[tuple[Path, ast.AST]] = []
    for rel_path, tree in project_structure[PROJECT_NORMAL_FILES_KEY]:
        logger.debug_log(f"Copying normal file: {rel_path}")
        out.append((rel_path, tree))

    for rel_path, versioned_trees in project_structure[PROJECT_VERSIONED_MODULES_KEY].items():
        module_key = rel_path.with_suffix("").as_posix()
        module_mapping = project_structure[PROJECT_MODULE_MAPPINGS_KEY].get(module_key)
        if module_mapping is None:
            raise ValueError(f"Missing module mapping for versioned module: {module_key}")
        _, transformed_ast = transform_versioned_module(
            rel_path,
            versioned_trees,
            module_mapping,
            project_structure[PROJECT_SYNC_MODULES_KEY],
            project_structure[PROJECT_INCOMPATIBILITIES_KEY],
            version_selection_strategy,
        )
        out.append((rel_path, transformed_ast))

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
