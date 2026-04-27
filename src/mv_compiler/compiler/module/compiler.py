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

    entity_mappings = (module_mapping or {}).get("entity_mappings", [])
    latest_version = versions[-1]
    latest_tree = versioned_trees[latest_version]
    top_level_by_version = {
        version: _collect_top_level_defs(tree)
        for version, tree in versioned_trees.items()
    }
    inferred_entities = _normalize_entity_mappings(entity_mappings, top_level_by_version, versions)
    versioned_value_names = collect_versioned_value_names(inferred_entities)

    new_body: list[ast.AST] = []
    import_nodes = _copy_declared_imports(module_mapping, versions)
    import_nodes.extend(_copy_sync_imports(inferred_entities, sync_functions_dict))
    new_body.extend(_dedupe_imports(import_nodes))

    class_exports = {
        name: spec for name, spec in inferred_entities.items()
        if spec.get("kind") == "class"
    }
    function_exports = {
        name: spec for name, spec in inferred_entities.items()
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

    for export_name, spec in inferred_entities.items():
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

    new_body.extend(_build_alias_assignments(inferred_entities))
    new_body.extend(_copy_unmapped_latest_defs(latest_tree, _mapped_output_names(inferred_entities, latest_version)))

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
        sync_key = spec.get("sync_key", export_name)
        sync_imports, _ = sync_functions_dict.get(sync_key, ([], []))
        for import_node in sync_imports:
            imports.append(copy.deepcopy(import_node))
    return imports


def _dedupe_imports(import_nodes: list[ast.AST]) -> list[ast.AST]:
    imports: dict[str, ast.AST] = {}
    for import_node in import_nodes:
        imports.setdefault(ast.unparse(import_node), import_node)
    return list(imports.values())


def _normalize_entity_mappings(
    entity_mappings: list,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict:
    if not isinstance(entity_mappings, list):
        raise ValueError("Module entity_mappings must be an array")

    out: dict = {}
    used_public_names: set[str] = set()
    used_entity_keys: set[str] = set()
    used_sources_by_version: dict[int, set[str]] = {version: set() for version in versions}
    for raw_spec in entity_mappings:
        if not isinstance(raw_spec, dict):
            raise ValueError("Module entity_mappings array items must be objects")
        spec = copy.deepcopy(raw_spec)
        kind = spec.get("kind")
        if kind not in {"class", "function", "variable"}:
            raise ValueError(f"Invalid entity kind: {kind}")
        if kind == "variable":
            versioned_by = spec.get("versioned_by")
            if versioned_by not in {"generated", "referenced"}:
                raise ValueError("Variable entity versioned_by must be 'generated' or 'referenced'")
        elif "versioned_by" in spec:
            raise ValueError("versioned_by is only valid for variable entities")

        # entity_mappings は外部仕様なので、生成処理が使いやすい内部specへ正規化する。
        source_names = _normalize_source_names(spec, versions)
        entity_key = spec.get("entity_key")
        if entity_key is None:
            entity_key = _default_entity_key(source_names, versions)
        if not isinstance(entity_key, str) or not entity_key:
            raise ValueError("Entity entity_key must be a non-empty string")
        if entity_key in used_entity_keys:
            raise ValueError(f"Duplicate entity_key: {entity_key}")
        used_entity_keys.add(entity_key)
        spec["source_names"] = source_names
        spec["sync_key"] = entity_key

        # 異名 mapping は実体と公開aliasを分ける。referenced変数だけはkey名にlatest右辺を束縛する。
        aliases = _build_alias_names(source_names)
        if _uses_entity_alias(entity_key, aliases):
            spec["entity_key"] = entity_key
            spec["entity_name"] = entity_key if spec.get("versioned_by") == "referenced" else f"_{entity_key}_Entity"
            spec["aliases"] = aliases
        else:
            spec["entity_key"] = entity_key
            spec["entity_name"] = entity_key
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
                raise ValueError(f"Duplicate entity source in v{version}: {source_name}")
            used_sources_by_version[version].add(source_name)
            node = top_level_by_version[version].get(source_name)
            if not _matches_kind(node, kind):
                raise ValueError(f"Entity {entity_key} ({kind}) source {source_name} is missing or mismatched in v{version}")
        out[spec["entity_name"]] = spec
    return out


def _default_entity_key(source_names: dict[str, str], versions: list[int]) -> str:
    parts: list[str] = []
    for version in versions:
        source_name = source_names[str(version)]
        parts.append(source_name[:1].upper() + source_name[1:].lower())
    return "".join(parts)


def _normalize_source_names(spec: dict, versions: list[int]) -> dict[str, str]:
    raw_source_names = spec.get("source_names")
    if not isinstance(raw_source_names, dict):
        raise ValueError("Entity source_names must be an object")

    source_names: dict[str, str] = {}
    for version in versions:
        source_name = raw_source_names.get(str(version))
        if not isinstance(source_name, str) or not source_name:
            raise ValueError(f"Entity source name for v{version} must be a non-empty string")
        source_names[str(version)] = source_name
    return source_names


def _build_alias_names(source_names: dict[str, str]) -> list[str]:
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
        source_name = spec.get("source_names", {}).get(str(latest_version))
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
