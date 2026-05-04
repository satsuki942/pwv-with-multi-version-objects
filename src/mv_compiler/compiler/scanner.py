import ast
import copy
import json
from pathlib import Path
from typing import Dict, Optional, Set, Tuple

from .common.util import logger
from .common.util.constants import (
    PROJECT_SYNC_MODULES_KEY,
    PROJECT_INCOMPATIBILITIES_KEY,
    PROJECT_NORMAL_FILES_KEY,
    PROJECT_VERSIONED_MODULES_KEY,
    PROJECT_MODULE_MAPPINGS_KEY,
)
from .versioning import parse_sync_module_filename

def create_project_structure(input_dir: Path) -> Dict:
    """
    1. 入力ディレクトリからPythonファイルを読み取る
    2. 各ファイルをASTに変換する
    3. ファイルを (通常ファイル / 同期関数 / 互換性定義) に分類する

    modules.json が存在する場合は、その宣言を正として versioned module を登録する。
    """
    project_structure = {
        PROJECT_SYNC_MODULES_KEY: {},
        PROJECT_INCOMPATIBILITIES_KEY: {},
        PROJECT_NORMAL_FILES_KEY: [],
        PROJECT_VERSIONED_MODULES_KEY: {},
        PROJECT_MODULE_MAPPINGS_KEY: {},
    }

    mapping_dir = input_dir / "_mv_mapping"

    sync_files = list(mapping_dir.glob("**/*_sync.py")) if mapping_dir.exists() else []
    mapping_file = mapping_dir / "modules.json"
    incompatibilities_files = [
        path for path in mapping_dir.glob("**/*.json")
        if path.name != "modules.json"
    ] if mapping_dir.exists() else []

    declared_versioned_files: set[Path] = set()
    if mapping_file.exists():
        module_mappings = _load_module_mappings(mapping_file)
        for module_mapping in module_mappings.values():
            _register_declared_versioned_module(input_dir, module_mapping, project_structure, declared_versioned_files)

    py_files = [
        path for path in input_dir.glob("**/*.py")
        if not _is_relative_to(path, mapping_dir)
    ]
    # modules.json に宣言されていない __<version>__ ファイルは通常モジュール名として扱う。
    source_files = [
        path for path in py_files
        if path.resolve() not in declared_versioned_files
    ]

    
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

    # --- 互換性定義ファイル ---
    for incompatibilities_file in incompatibilities_files:
        try:
            json_data = json.loads(incompatibilities_file.read_text(encoding="utf-8"))
            incompatibilities = _parse_incompatibility_data(incompatibilities_file, json_data)
            if incompatibilities:
                project_structure[PROJECT_INCOMPATIBILITIES_KEY].update(incompatibilities)
        except Exception as e:
            logger.error_log(f"Failed to parse {incompatibilities_file}: {e}")

    return project_structure


def _is_relative_to(path: Path, parent: Path) -> bool:
    """path が parent 配下にあるかを、古いPythonでも使える形で判定する。"""
    try:
        path.relative_to(parent)
        return True
    except ValueError:
        return False


# --------------------
# --- ヘルパー関数 ---
# --------------------

def _parse_sync_modules(base_name: str, source_code: str) -> Tuple:
    """同期モジュールから import と同期関数のASTノードを抽出する。"""
    tree = ast.parse(source_code)
    modules = []
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules.append(node)
        elif isinstance(node, ast.FunctionDef):
            functions.append(node)
    return (modules, functions)

def _load_module_mappings(mapping_file: Path) -> dict[str, dict]:
    """
    modules.json を読み込み、各 module mapping を module_path で引ける形に正規化する。

    schema_version はトップレベル宣言として扱い、各 module mapping に注入する。
    """
    try:
        json_data = json.loads(mapping_file.read_text(encoding="utf-8"))
    except Exception as e:
        raise ValueError(f"Failed to parse {mapping_file}: {e}") from e

    if not isinstance(json_data, dict) or not isinstance(json_data.get("modules"), dict):
        raise ValueError(f"Invalid module mapping schema: {mapping_file}")

    out: dict[str, dict] = {}
    used_module_paths: set[str] = set()

    # schema_version は mapping 全体にかかる指定として扱う。
    schema_version = json_data.get("schema_version", 1)
    if not isinstance(schema_version, int) or isinstance(schema_version, bool):
        raise ValueError(f"schema_version must be an integer in {mapping_file}")

    for module_key, module_mapping in json_data["modules"].items():
        # module_key と module mapping の基本形を検証する。
        if not isinstance(module_key, str) or not module_key:
            raise ValueError(f"Module key must be a non-empty string in {mapping_file}")
        if not isinstance(module_mapping, dict):
            raise ValueError(f"Module mapping must be an object: {module_key}")

        # 後続処理が参照しやすいよう、派生情報を mapping に持たせる。
        module_mapping = copy.deepcopy(module_mapping)
        module_mapping["module_key"] = module_key
        module_mapping["schema_version"] = schema_version

        # 出力先になる module_path は重複できない。
        module_path = module_mapping.get("module_path")
        if not isinstance(module_path, str) or not module_path:
            raise ValueError(f"Module module_path must be a non-empty string: {module_key}")
        if module_path in used_module_paths:
            raise ValueError(f"Duplicate module_path in modules.json: {module_path}")
        used_module_paths.add(module_path)

        # versioned module として読み込む版の一覧を検証する。
        versions = module_mapping.get("versions")
        if (
            not isinstance(versions, list)
            or not versions
            or not all(isinstance(version, int) and not isinstance(version, bool) for version in versions)
        ):
            raise ValueError(f"Module versions must be a non-empty array of integers: {module_key}")
        if len(set(versions)) != len(versions):
            raise ValueError(f"Duplicate module version in modules.json: {module_key}")

        out[module_path] = module_mapping
    return out


def _register_declared_versioned_module(
    input_dir: Path,
    module_mapping: dict,
    project_structure: Dict,
    declared_versioned_files: set[Path],
) -> None:
    """JSON宣言を正として、対象versionのソースだけをversioned moduleに登録する。"""
    module_path = Path(*module_mapping["module_path"].split("/"))
    logical_rel_path = module_path.with_suffix(".py")
    versions = sorted(module_mapping["versions"])

    # 論理モジュールの出力先と通常ソースが衝突する場合は曖昧なので失敗させる。
    output_source_path = input_dir / logical_rel_path
    if output_source_path.exists():
        raise ValueError(f"Output path conflicts with a normal source file: {logical_rel_path.as_posix()}")

    project_structure[PROJECT_MODULE_MAPPINGS_KEY][module_mapping["module_path"]] = module_mapping
    for version in versions:
        # 宣言された各版のファイルだけを versioned module として登録する。
        versioned_rel_path = module_path.with_name(f"{module_path.name}__{version}__.py")
        versioned_path = input_dir / versioned_rel_path
        if not versioned_path.exists():
            raise ValueError(f"Declared versioned module file does not exist: {versioned_rel_path.as_posix()}")

        try:
            source_code = versioned_path.read_text(encoding="utf-8")
            tree = ast.parse(source_code)
        except Exception as e:
            raise ValueError(
                f"Failed to parse declared versioned module: {versioned_rel_path.as_posix()}: {e}"
            ) from e

        declared_versioned_files.add(versioned_path.resolve())
        project_structure[PROJECT_VERSIONED_MODULES_KEY].setdefault(logical_rel_path, {})[version] = tree

def _parse_incompatibility_data(file_path: Path, data: dict) -> Optional[Dict[str, Dict[str, Set[str]]]]:
    """
    旧形式の incompatibility JSON を、既存変換器が使う辞書構造に変換する。

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
