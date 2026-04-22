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
    import_nodes = _copy_declared_imports(module_mapping, versions)
    import_nodes.extend(_copy_sync_imports(inferred_exports, sync_functions_dict))
    new_body.extend(_dedupe_imports(import_nodes))
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


def _copy_declared_imports(module_mapping: dict | None, versions: list[int]) -> list[ast.AST]:
    imports_by_version = (module_mapping or {}).get("imports", {})
    if imports_by_version is None:
        imports_by_version = {}
    if not isinstance(imports_by_version, dict):
        raise ValueError("Module imports must be an object")

    imports: list[ast.AST] = []
    for version in versions:
        raw_imports = imports_by_version.get(str(version), [])
        if not isinstance(raw_imports, list) or not all(isinstance(item, str) for item in raw_imports):
            raise ValueError(f"Module imports for v{version} must be a list of strings")
        for import_source in raw_imports:
            imports.append(_parse_import_spec(import_source, version))
    return imports


def _parse_import_spec(import_source: str, version: int) -> ast.AST:
    try:
        tree = ast.parse(import_source)
    except SyntaxError as e:
        raise ValueError(f"Invalid import spec for v{version}: {import_source}") from e

    if len(tree.body) != 1 or not isinstance(tree.body[0], (ast.Import, ast.ImportFrom)):
        raise ValueError(f"Import spec for v{version} must contain exactly one import statement: {import_source}")
    return tree.body[0]


def _copy_sync_imports(exports: dict, sync_functions_dict: dict) -> list[ast.AST]:
    imports: list[ast.AST] = []
    for export_name, spec in exports.items():
        if spec.get("kind") != "class":
            continue
        sync_imports, _ = sync_functions_dict.get(export_name, ([], []))
        for import_node in sync_imports:
            imports.append(copy.deepcopy(import_node))
    return imports


def _dedupe_imports(import_nodes: list[ast.AST]) -> list[ast.AST]:
    imports: dict[str, ast.AST] = {}
    for import_node in import_nodes:
        imports.setdefault(ast.unparse(import_node), import_node)
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
