import ast
import copy
from pathlib import Path

from ..common.util import logger
from ..common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY
from ..elements.class_.compiler import build_unified_classes_for_module
from ..elements.function.compiler import build_function_export
from ..elements.variable.compiler import (
    build_module_runtime,
    build_variable_export,
    collect_versioned_value_names,
)


def transform_versioned_module(
    logical_rel_path: Path,
    versioned_trees: dict[int, ast.AST],
    module_mapping: dict | None,
    sync_functions_dict: dict,
    incompatibilities: dict | None,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
) -> tuple[Path, ast.AST | None]:
    """版付きモジュールASTを単一モジュールASTへ統合する。"""
    versions = sorted(versioned_trees)
    if not versions:
        logger.error_log(f"Versioned module has no versions: {logical_rel_path}")
        return logical_rel_path, None

    exports = (module_mapping or {}).get("exports", {})
    latest_version = versions[-1]
    latest_tree = versioned_trees[latest_version]
    top_level_by_version = {
        version: _collect_top_level_defs(tree)
        for version, tree in versioned_trees.items()
    }
    inferred_exports = _normalize_exports(exports, top_level_by_version, versions)
    versioned_value_names = collect_versioned_value_names(inferred_exports)

    new_body: list[ast.AST] = []
    new_body.extend(_copy_imports(latest_tree))
    new_body.extend(_copy_sync_imports(inferred_exports, sync_functions_dict))
    new_body.extend(build_module_runtime(version_selection_strategy, latest_version))

    class_exports = {
        name: spec for name, spec in inferred_exports.items()
        if spec.get("kind") == "class"
    }
    if class_exports:
        new_body.extend(build_unified_classes_for_module(
            class_exports,
            top_level_by_version,
            versions,
            versioned_value_names,
            sync_functions_dict,
            incompatibilities,
            version_selection_strategy,
        ))

    for export_name, spec in inferred_exports.items():
        kind = spec.get("kind")
        if kind == "function":
            new_body.extend(build_function_export(
                export_name,
                spec,
                top_level_by_version,
                versions,
                versioned_value_names,
                version_selection_strategy,
            ))
        elif kind == "variable":
            variable_node = build_variable_export(
                export_name,
                spec,
                top_level_by_version,
                versions,
                latest_version,
                version_selection_strategy,
            )
            if variable_node:
                new_body.append(variable_node)

    new_body.extend(_copy_unmapped_latest_defs(latest_tree, set(inferred_exports)))

    new_module = ast.Module(body=new_body, type_ignores=[])
    ast.fix_missing_locations(new_module)
    return logical_rel_path, new_module


def _collect_top_level_defs(tree: ast.AST) -> dict[str, ast.AST]:
    defs: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
            defs[node.name] = node
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    defs[target.id] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            defs[node.target.id] = node
    return defs


def _copy_imports(tree: ast.AST) -> list[ast.AST]:
    return [
        copy.deepcopy(node)
        for node in tree.body
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]


def _copy_sync_imports(exports: dict, sync_functions_dict: dict) -> list[ast.AST]:
    imports: dict[str, ast.AST] = {}
    for export_name, spec in exports.items():
        if spec.get("kind") != "class":
            continue
        sync_imports, _ = sync_functions_dict.get(export_name, ([], []))
        for import_node in sync_imports:
            imports[ast.unparse(import_node)] = copy.deepcopy(import_node)
    return list(imports.values())


def _normalize_exports(
    explicit_exports: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict:
    out: dict = {}
    for export_name, raw_spec in explicit_exports.items():
        spec = copy.deepcopy(raw_spec)
        kind = spec.get("kind")
        if kind not in {"class", "function", "variable"}:
            raise ValueError(f"Invalid export kind for {export_name}: {kind}")

        specified_versions = spec.get("versions")
        if specified_versions is not None:
            for version, source_name in specified_versions.items():
                if source_name != export_name:
                    raise ValueError(
                        "Only same-name export mappings are supported for now: "
                        f"{export_name} v{version} -> {source_name}"
                    )
        spec["versions"] = {str(version): export_name for version in versions}
        if kind == "variable":
            spec.setdefault("binding", "plain")

        for version in versions:
            node = top_level_by_version[version].get(export_name)
            if not _matches_kind(node, kind):
                raise ValueError(f"Export {export_name} ({kind}) is missing or mismatched in v{version}")
        out[export_name] = spec
    return out


def _matches_kind(node: ast.AST | None, kind: str) -> bool:
    if kind == "class":
        return isinstance(node, ast.ClassDef)
    if kind == "function":
        return isinstance(node, ast.FunctionDef)
    if kind == "variable":
        return isinstance(node, (ast.Assign, ast.AnnAssign))
    return False


def _copy_unmapped_latest_defs(latest_tree: ast.AST, mapped_names: set[str]) -> list[ast.AST]:
    out: list[ast.AST] = []
    for node in latest_tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            continue
        if _top_level_name(node) in mapped_names:
            continue
        out.append(copy.deepcopy(node))
    return out


def _top_level_name(node: ast.AST) -> str | None:
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        return node.name
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    return None
