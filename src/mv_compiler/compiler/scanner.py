import ast
import json
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from .common.util import logger
from .common.util.constants import (
    PROJECT_SYNC_MODULES_KEY,
    PROJECT_INCOMPATIBILITIES_KEY,
    PROJECT_NORMAL_FILES_KEY,
    PROJECT_VERSIONED_MODULES_KEY,
    PROJECT_EVOLUTION_SPECS_KEY,
)
from .versioning import parse_sync_module_filename, parse_versioned_module_filename

def create_project_structure(input_dir: Path) -> Dict:
    """
    1. 入力ディレクトリからPythonファイルを読み取る
    2. 各ファイルをASTに変換する
    3. ファイルを (通常ファイル / 同期関数 / 互換性定義) に分類する
    """
    project_structure = {
        PROJECT_SYNC_MODULES_KEY: {},
        PROJECT_INCOMPATIBILITIES_KEY: {},
        PROJECT_NORMAL_FILES_KEY: [],
        PROJECT_VERSIONED_MODULES_KEY: {},
        PROJECT_EVOLUTION_SPECS_KEY: {},
    }

    mapping_dir = input_dir / "_mv_mapping"

    py_files = [
        path for path in input_dir.glob("**/*.py")
        if not _is_relative_to(path, mapping_dir)
    ]
    source_files = []
    for file_path in py_files:
        if parse_versioned_module_filename(file_path.name)[0] is not None:
            _register_versioned_module(input_dir, file_path, project_structure)
        else:
            source_files.append(file_path)
    sync_files = list(mapping_dir.glob("**/*_sync.py")) if mapping_dir.exists() else []
    evolution_file = mapping_dir / "evolution.json"
    incompatibilities_files = [
        path for path in mapping_dir.glob("**/*.json")
        if path.name not in {"evolution.json", "modules.json"}
    ] if mapping_dir.exists() else []

    
    # --- 通常ファイル ---
    for source_file in source_files:
        try:
            with open(source_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
            relative_path = source_file.relative_to(input_dir)
            project_structure[PROJECT_NORMAL_FILES_KEY].append((relative_path, ast.parse(source_code)))
        except Exception as e:
            logger.error_log(f"Failed to parse {source_file}: {e}")

    # --- 状態同期ファイル ---
    for state_transformation_file in sync_files:
        base_name = parse_sync_module_filename(state_transformation_file.name)
        if base_name is None:
            continue
        try:
            with open(state_transformation_file, 'r', encoding='utf-8') as f:
                source_code = f.read()
            project_structure[PROJECT_SYNC_MODULES_KEY][base_name] = _parse_sync_modules(base_name, source_code)
        except Exception as e:
            logger.error_log(f"Failed to parse {state_transformation_file}: {e}")

    # --- evolution specification ---
    if evolution_file.exists():
        try:
            json_data = json.loads(evolution_file.read_text(encoding="utf-8"))
            if isinstance(json_data, dict) and isinstance(json_data.get("modules"), dict):
                project_structure[PROJECT_EVOLUTION_SPECS_KEY].update(json_data["modules"])
            else:
                logger.error_log(f"Invalid evolution schema: {evolution_file}")
        except Exception as e:
            logger.error_log(f"Failed to parse {evolution_file}: {e}")

    # --- 互換性定義ファイル ---
    for incompatibilities_file in incompatibilities_files:
        try:
            json_data = json.loads(incompatibilities_file.read_text(encoding="utf-8"))
            incompatibilities = _parse_incompatibility_data(incompatibilities_file, json_data)
            if incompatibilities:
                project_structure[PROJECT_INCOMPATIBILITIES_KEY].update(incompatibilities)
        except Exception as e:
            logger.error_log(f"Failed to parse {incompatibilities_file}: {e}")

    _infer_missing_evolution_specs(project_structure)
    return project_structure


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


# --------------------
# --- ヘルパー関数 ---
# --------------------

def _parse_sync_modules(base_name: str, source_code: str) -> Tuple:
    tree = ast.parse(source_code)
    modules = []
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules.append(node)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node)
    return (modules, functions)

def _register_versioned_module(input_dir: Path, file_path: Path, project_structure: Dict) -> None:
    """foo__1__.py を論理モジュール foo.py のversion 1として登録する。"""
    base_name, version = parse_versioned_module_filename(file_path.name)
    if base_name is None or version is None:
        return

    relative_path = file_path.relative_to(input_dir)
    logical_rel_path = relative_path.with_name(f"{base_name}.py")

    try:
        source_code = file_path.read_text(encoding="utf-8")
        tree = ast.parse(source_code)
    except Exception as e:
        logger.error_log(f"Failed to parse {file_path}: {e}")
        return

    project_structure[PROJECT_VERSIONED_MODULES_KEY].setdefault(logical_rel_path, {})[version] = tree

def _parse_incompatibility_data(file_path: Path, data: dict) -> Optional[Dict[str, Dict[str, Set[str]]]]:
    """
    JSONスキーマ:
      {
        "<base_name>": {
          "<version>": ["attr1", "attr2", ...]
        }
      }

    戻り値:
      { base_name: { version: set(attrs) } }
    """
    if not isinstance(data, dict):
        logger.error_log(f"Top-level JSON must be an object: {file_path}")
        return None

    out: Dict[str, Dict[str, Set[str]]] = {}

    for base_name, versions in data.items():
        if not isinstance(base_name, str) or not isinstance(versions, dict):
            logger.error_log(f"Invalid base_name/versions in {file_path}: {base_name}")
            continue

        out[base_name] = {}
        for ver, attrs in versions.items():
            if not isinstance(ver, str):
                logger.error_log(f"Invalid version key in {file_path}: {base_name}.{ver}")
                continue
            if not isinstance(attrs, list) or not all(isinstance(a, str) for a in attrs):
                logger.error_log(f"Invalid attrs list in {file_path}: {base_name}.{ver}")
                continue
            try:
                ver = int(ver)
            except ValueError:
                logger.error_log(f"Version must be an integer string in {file_path}: {base_name}.{ver}")
                continue

            out[base_name][ver] = set(attrs)

    return out


def _infer_missing_evolution_specs(project_structure: Dict) -> None:
    """Create a small same-name evolution spec when no explicit spec exists.

    This keeps old source fixtures usable without reading modules.json.
    """
    for rel_path, versioned_trees in project_structure[PROJECT_VERSIONED_MODULES_KEY].items():
        module_key = rel_path.with_suffix("").as_posix()
        if module_key in project_structure[PROJECT_EVOLUTION_SPECS_KEY]:
            continue

        versions = sorted(versioned_trees)
        by_version = {
            version: _collect_top_level_kinds(tree)
            for version, tree in versioned_trees.items()
        }
        names = sorted({name for defs in by_version.values() for name in defs})
        entities = {}
        for name in names:
            entries = {}
            kinds = set()
            for version in versions:
                kind = by_version[version].get(name)
                if kind is None:
                    continue
                kinds.add(kind)
                entries[str(version)] = {"kind": kind, "name": name}
            if entries and len(kinds) == 1:
                entities[name] = {
                    "state": {"sync": "none"},
                    "versions": entries,
                }

        imports = {}
        for version, tree in versioned_trees.items():
            import_sources = [
                ast.unparse(node)
                for node in tree.body
                if isinstance(node, (ast.Import, ast.ImportFrom))
            ]
            if import_sources:
                imports[str(version)] = import_sources

        project_structure[PROJECT_EVOLUTION_SPECS_KEY][module_key] = {
            "versions": versions,
            "imports": imports,
            "entities": entities,
        }


def _collect_top_level_kinds(tree: ast.AST) -> Dict[str, str]:
    defs: Dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            defs[node.name] = "class"
        elif isinstance(node, ast.FunctionDef):
            defs[node.name] = "function"
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defs[target.id] = "variable"
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defs[node.target.id] = "variable"
    return defs
