import ast
import copy
from pathlib import Path

from ..common.util import logger
from ..common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY
from ..elements.class_.compiler import build_unified_classes_for_module
from ..elements.function.compiler import build_function_export
from ..elements.signature import build_signature_runtime_support
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

    class_exports = {
        name: spec for name, spec in inferred_exports.items()
        if spec.get("kind") == "class"
    }
    function_exports = {
        name: spec for name, spec in inferred_exports.items()
        if spec.get("kind") == "function"
    }
    if class_exports or function_exports:
        new_body.extend(build_signature_runtime_support())
    new_body.extend(build_module_runtime(version_selection_strategy, latest_version))

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

    new_body.extend(_build_alias_assignments(inferred_exports))
    new_body.extend(_copy_unmapped_latest_defs(latest_tree, _mapped_output_names(inferred_exports, latest_version)))

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
        sync_key = spec.get("key", export_name)
        sync_imports, _ = sync_functions_dict.get(sync_key, ([], []))
        for import_node in sync_imports:
            imports.append(copy.deepcopy(import_node))
    return imports


def _dedupe_imports(import_nodes: list[ast.AST]) -> list[ast.AST]:
    imports: dict[str, ast.AST] = {}
    for import_node in import_nodes:
        imports.setdefault(ast.unparse(import_node), import_node)
    return list(imports.values())


def _normalize_exports(
    explicit_exports: dict | list,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict:
    out: dict = {}
    used_public_names: set[str] = set()
    used_sources_by_version: dict[int, set[str]] = {version: set() for version in versions}
    for export_name, raw_spec in _iter_export_specs(explicit_exports, versions):
        spec = copy.deepcopy(raw_spec)
        kind = spec.get("kind")
        if kind not in {"class", "function", "variable"}:
            raise ValueError(f"Invalid export kind for {export_name}: {kind}")

        # public な旧名/新名とは別に、key は sync 探索と隠し実体名の基準として保持する。
        source_names = _normalize_export_versions(export_name, spec, versions)
        spec["versions"] = source_names
        if kind == "variable":
            spec.setdefault("binding", "plain")

        # 異名 mapping は隠し実体へ統合し、各版の source name だけを alias として公開する。
        aliases = _build_alias_names(export_name, source_names)
        if _uses_entity_alias(export_name, aliases):
            spec["key"] = export_name
            spec["entity_name"] = f"_{export_name}_Entity"
            spec["aliases"] = aliases
        else:
            spec["key"] = export_name
            spec["entity_name"] = export_name
            spec["aliases"] = []

        # 同じ公開名を複数 entity から出すと、版選択では解決できない曖昧さになるため拒否する。
        public_names = spec["aliases"] or [spec["entity_name"]]
        for public_name in public_names:
            if public_name in used_public_names:
                raise ValueError(f"Alias name collision: {public_name}")
            used_public_names.add(public_name)

        for version in versions:
            source_name = source_names[str(version)]
            if source_name in used_sources_by_version[version]:
                raise ValueError(f"Duplicate export source in v{version}: {source_name}")
            used_sources_by_version[version].add(source_name)
            node = top_level_by_version[version].get(source_name)
            if not _matches_kind(node, kind):
                raise ValueError(f"Export {export_name} ({kind}) source {source_name} is missing or mismatched in v{version}")
        out[spec["entity_name"]] = spec
    return out


def _iter_export_specs(explicit_exports: dict | list, versions: list[int]) -> list[tuple[str, dict]]:
    if isinstance(explicit_exports, dict):
        return list(explicit_exports.items())
    if isinstance(explicit_exports, list):
        out: list[tuple[str, dict]] = []
        for raw_spec in explicit_exports:
            if not isinstance(raw_spec, dict):
                raise ValueError("Module exports array items must be objects")
            spec = copy.deepcopy(raw_spec)
            # array 形式では key 省略を許し、版ごとの source name から semantic key を作る。
            export_name = spec.pop("key", None)
            if export_name is None:
                export_name = _default_export_key(spec, versions)
            if not isinstance(export_name, str) or not export_name:
                raise ValueError("Export key must be a non-empty string")
            out.append((export_name, spec))
        return out
    raise ValueError("Module exports must be an object or an array")


def _default_export_key(spec: dict, versions: list[int]) -> str:
    raw_versions = spec.get("versions")
    if not isinstance(raw_versions, dict):
        raise ValueError("Array export without key must define versions")
    parts: list[str] = []
    for version in versions:
        source_name = raw_versions.get(str(version))
        if not isinstance(source_name, str) or not source_name:
            raise ValueError(f"Export source name for v{version} must be a non-empty string")
        parts.append(source_name[:1].upper() + source_name[1:].lower())
    return "".join(parts)


def _normalize_export_versions(export_name: str, spec: dict, versions: list[int]) -> dict[str, str]:
    raw_versions = spec.get("versions")
    if raw_versions is None:
        raw_versions = {}
    if not isinstance(raw_versions, dict):
        raise ValueError(f"Export versions for {export_name} must be an object")

    source_names: dict[str, str] = {}
    for version in versions:
        source_name = raw_versions.get(str(version), export_name)
        if not isinstance(source_name, str) or not source_name:
            raise ValueError(f"Export source name for {export_name} v{version} must be a non-empty string")
        source_names[str(version)] = source_name
    return source_names


def _build_alias_names(export_name: str, source_names: dict[str, str]) -> list[str]:
    aliases: list[str] = []
    for name in source_names.values():
        if name not in aliases:
            aliases.append(name)
    return aliases


def _uses_entity_alias(export_name: str, aliases: list[str]) -> bool:
    return len(aliases) > 1 or aliases != [export_name]


def _build_alias_assignments(exports: dict) -> list[ast.Assign]:
    assignments: list[ast.Assign] = []
    for entity_name, spec in exports.items():
        # 生成した隠し実体を、各版で実際に使われていた名前から参照できるようにする。
        for alias in spec.get("aliases", []):
            if alias == entity_name:
                continue
            assignments.append(ast.Assign(
                targets=[ast.Name(id=alias, ctx=ast.Store())],
                value=ast.Name(id=entity_name, ctx=ast.Load()),
            ))
    return assignments


def _mapped_output_names(exports: dict, latest_version: int) -> set[str]:
    names: set[str] = set(exports)
    for entity_name, spec in exports.items():
        names.add(entity_name)
        names.update(spec.get("aliases", []))
        # latest 側の source 定義を通常定義として再コピーすると alias と重複するため除外する。
        source_name = spec.get("versions", {}).get(str(latest_version))
        if source_name:
            names.add(source_name)
    return names


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
