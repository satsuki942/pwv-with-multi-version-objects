import ast
from pathlib import Path
from typing import Any

from .ir import LogicalModuleIR, LogicalObjectIR, LogicalObjectKind


def build_logical_module_ir(
    logical_rel_path: Path,
    versioned_trees: dict[int, ast.AST],
    module_mapping: dict[str, Any],
) -> LogicalModuleIR:
    """
    schema_version 2 の入力から LogicalModuleIR を構築する。

    現時点では base version のトップレベル順序を論理モジュールの公開順序として採用し、
    各要素に対応する他版のASTノードと互換仕様を紐付ける。
    """
    # 利用可能な版を確定し、論理モジュールの基準にする版を選ぶ。
    versions = sorted(versioned_trees)
    if not versions:
        raise ValueError(f"Logical module has no versions: {logical_rel_path.as_posix()}")

    base_version = 1 if 1 in versions else versions[0]
    base_tree = versioned_trees[base_version]

    # 各版のトップレベル定義を名前で引けるようにして、base側の要素へ束ねる。
    top_level_by_version = {
        version: _collect_top_level_defs(tree)
        for version, tree in versioned_trees.items()
    }
    compatibility_by_name = _index_compatibility_operations(module_mapping)

    # base version のトップレベル順序を維持して LogicalObjectIR を作る。
    objects: list[LogicalObjectIR] = []
    for order_index, node in enumerate(base_tree.body):
        kind = _logical_object_kind(node)
        public_name = _top_level_name(node)
        version_nodes = _collect_version_nodes(public_name, top_level_by_version, versions)
        objects.append(LogicalObjectIR(
            kind=kind,
            order_index=order_index,
            public_name=public_name,
            base_version_node=node,
            version_nodes=version_nodes,
            compatibility_spec=compatibility_by_name.get(public_name) if public_name else None,
        ))

    module_path = module_mapping["module_path"]
    return LogicalModuleIR(
        module_key=module_mapping.get("module_key", module_path),
        module_path=module_path,
        logical_rel_path=logical_rel_path,
        versions=versions,
        base_version=base_version,
        objects=objects,
    )


def _index_compatibility_operations(module_mapping: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """互換仕様の operation を、論理操作名から引ける辞書に変換する。"""
    # schema v2 の compatibility はまだ拡張中なので、最小限の形だけ検証する。
    compatibility = module_mapping.get("compatibility", {})
    if compatibility is None:
        compatibility = {}
    if not isinstance(compatibility, dict):
        raise ValueError("Module compatibility must be an object")

    operations = compatibility.get("operations", [])
    if operations is None:
        operations = []
    if not isinstance(operations, list):
        raise ValueError("Module compatibility.operations must be an array")

    indexed: dict[str, dict[str, Any]] = {}
    for operation in operations:
        if not isinstance(operation, dict):
            raise ValueError("Module compatibility.operations items must be objects")
        # 名前フィールドの候補は、仕様の揺れを吸収するため当面は複数受ける。
        name = operation.get("name") or operation.get("public_name") or operation.get("logical_operation")
        if isinstance(name, str) and name:
            indexed[name] = operation
    return indexed


def _collect_top_level_defs(tree: ast.AST) -> dict[str, ast.AST]:
    """ASTモジュールから名前を持つトップレベル要素だけを集める。"""
    defs: dict[str, ast.AST] = {}
    for node in tree.body:
        name = _top_level_name(node)
        if name is not None:
            defs[name] = node
    return defs


def _collect_version_nodes(
    public_name: str | None,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict[int, ast.AST | None]:
    """論理要素名に対応する各版のASTノードを集める。"""
    if public_name is None:
        return {version: None for version in versions}
    return {
        version: top_level_by_version[version].get(public_name)
        for version in versions
    }


def _logical_object_kind(node: ast.AST) -> LogicalObjectKind:
    """トップレベルASTノードを LogicalObjectKind に分類する。"""
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return LogicalObjectKind.IMPORT
    if isinstance(node, ast.ClassDef):
        return LogicalObjectKind.CLASS
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return LogicalObjectKind.FUNCTION
    if _is_variable_node(node):
        return LogicalObjectKind.VARIABLE
    return LogicalObjectKind.OTHER


def _is_variable_node(node: ast.AST) -> bool:
    """トップレベル変数として扱える代入ノードか判定する。"""
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return True
    if isinstance(node, ast.Assign):
        return any(isinstance(target, ast.Name) for target in node.targets)
    return False


def _top_level_name(node: ast.AST) -> str | None:
    """トップレベルASTノードから公開名を取り出す。"""
    if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign):
        for target in node.targets:
            if isinstance(target, ast.Name):
                return target.id
    return None
