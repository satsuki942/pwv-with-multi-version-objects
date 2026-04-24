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

_MVO_ACCESS_RUNTIME = """
class MVOAccess:
    def __init__(self, candidates, strategy='continuity'):
        object.__setattr__(self, '_candidates', {int(k): v for k, v in candidates.items()})
        object.__setattr__(self, '_strategy', strategy)
        current_version = max(self._candidates.keys()) if strategy == 'latest' else min(self._candidates.keys())
        object.__setattr__(self, '_current_version', current_version)

    def _candidate(self, version):
        return self._candidates[int(version)]

    def _candidate_value(self, version):
        candidate = self._candidate(version)
        return candidate['value']

    def _versions_latest_first(self):
        return sorted(self._candidates.keys(), reverse=True)

    def _resolve_read_version(self):
        if self._current_version in self._candidates:
            return self._current_version
        return self._versions_latest_first()[0]

    def _resolve_call_version(self, args, kwargs):
        current = self._current_version
        if current in self._candidates and callable(self._candidate_value(current)):
            return current
        for version in self._versions_latest_first():
            if callable(self._candidate_value(version)):
                object.__setattr__(self, '_current_version', version)
                return version
        raise TypeError('No version of this access is callable.')

    def get(self):
        return self._candidate_value(self._resolve_read_version())

    def set(self, new_value):
        version = self._resolve_read_version()
        self._candidate(version)['value'] = new_value
        return new_value

    def __call__(self, *args, **kwargs):
        return self._candidate_value(self._resolve_call_version(args, kwargs))(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(self.get(), name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            setattr(self.get(), name, value)

    def __bool__(self):
        return bool(self.get())

    def __str__(self):
        return str(self.get())

    def __repr__(self):
        return repr(self.get())
"""


def transform_versioned_module(
    logical_rel_path: Path,
    versioned_trees: dict[int, ast.AST],
    evolution_spec: dict | None,
    sync_functions_dict: dict,
    incompatibilities: dict | None,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
) -> tuple[Path, ast.AST | None]:
    """版付きモジュールASTを単一モジュールASTへ統合する。"""
    versions = sorted(versioned_trees)
    if not versions:
        logger.error_log(f"Versioned module has no versions: {logical_rel_path}")
        return logical_rel_path, None

    evolution_spec = evolution_spec or {}
    latest_version = versions[-1]
    latest_tree = versioned_trees[latest_version]
    top_level_by_version = {
        version: _collect_top_level_defs(tree)
        for version, tree in versioned_trees.items()
    }
    normalized = _normalize_evolution_spec(evolution_spec, top_level_by_version, versions)
    inferred_exports = normalized["legacy_exports"]
    access_facades = normalized["access_facades"]
    versioned_value_names = collect_versioned_value_names(inferred_exports)

    new_body: list[ast.AST] = []
    import_nodes = _copy_declared_imports(evolution_spec, versions)
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
    if access_facades:
        new_body.extend(ast.parse(_MVO_ACCESS_RUNTIME).body)

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

    for public_name, entries in access_facades.items():
        new_body.extend(_build_access_facade(
            public_name,
            entries,
            top_level_by_version,
            version_selection_strategy,
        ))

    mapped_names = set(inferred_exports) | set(access_facades)
    for entries in access_facades.values():
        mapped_names.update(entry["name"] for entry in entries)
    new_body.extend(_copy_unmapped_latest_defs(latest_tree, mapped_names))

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


def _copy_declared_imports(evolution_spec: dict | None, versions: list[int]) -> list[ast.AST]:
    imports_by_version = (evolution_spec or {}).get("imports", {})
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
        if specified_versions is None:
            specified_versions = {str(version): export_name for version in versions}
        spec["versions"] = {str(version): specified_versions.get(str(version), export_name) for version in versions}
        if kind == "variable":
            spec.setdefault("binding", "plain")

        for version in versions:
            node = top_level_by_version[version].get(export_name)
            source_name = spec["versions"][str(version)]
            node = top_level_by_version[version].get(source_name)
            if not _matches_kind(node, kind):
                raise ValueError(f"Export {export_name} ({kind}) is missing or mismatched in v{version}: {source_name}")
        out[export_name] = spec
    return out


def _normalize_evolution_spec(
    evolution_spec: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
) -> dict:
    entities = evolution_spec.get("entities", {})
    if not isinstance(entities, dict):
        raise ValueError("Evolution spec entities must be an object")

    entity_entries: dict[str, list[dict]] = {}
    public_name_entities: dict[str, set[str]] = {}
    for entity_id, entity_spec in entities.items():
        entity_versions = entity_spec.get("versions", {})
        state_sync = (entity_spec.get("state") or {}).get("sync", "none")
        if not isinstance(entity_versions, dict):
            raise ValueError(f"Entity versions must be an object: {entity_id}")
        for raw_version, entry in entity_versions.items():
            version = int(raw_version)
            if version not in top_level_by_version:
                raise ValueError(f"Unknown version in entity {entity_id}: {version}")
            kind = entry.get("kind")
            name = entry.get("name")
            if kind not in {"function", "variable", "class"}:
                raise ValueError(f"Invalid kind in entity {entity_id} v{version}: {kind}")
            if not isinstance(name, str):
                raise ValueError(f"Invalid name in entity {entity_id} v{version}: {name}")
            node = top_level_by_version[version].get(name)
            if not _matches_kind(node, kind):
                raise ValueError(f"Entity {entity_id} ({kind}) is missing or mismatched in v{version}: {name}")
            normalized_entry = {
                "entity_id": entity_id,
                "state_sync": state_sync,
                "version": version,
                "kind": kind,
                "name": name,
            }
            entity_entries.setdefault(entity_id, []).append(normalized_entry)
            public_name_entities.setdefault(name, set()).add(entity_id)

    public_to_entries: dict[str, list[dict]] = {}
    for entity_id, entries in entity_entries.items():
        names = {entry["name"] for entry in entries}
        for public_name in names:
            if len(public_name_entities[public_name]) == 1:
                public_to_entries.setdefault(public_name, []).extend(copy.deepcopy(entries))
            else:
                public_to_entries.setdefault(public_name, []).extend(
                    copy.deepcopy(entry) for entry in entries if entry["name"] == public_name
                )

    legacy_exports: dict[str, dict] = {}
    access_facades: dict[str, list[dict]] = {}
    for public_name, entries in public_to_entries.items():
        kinds = {entry["kind"] for entry in entries}
        entities_for_name = {entry["entity_id"] for entry in entries}
        if len(kinds) == 1 and len(entities_for_name) == 1:
            kind = entries[0]["kind"]
            version_map = {str(entry["version"]): entry["name"] for entry in entries}
            legacy_exports[public_name] = {
                "kind": kind,
                "versions": version_map,
            }
            if kind == "variable":
                legacy_exports[public_name]["binding"] = "versioned_value"
        else:
            access_facades[public_name] = entries

    return {
        "legacy_exports": _normalize_exports(legacy_exports, top_level_by_version, versions),
        "access_facades": access_facades,
    }


def _build_access_facade(
    public_name: str,
    entries: list[dict],
    top_level_by_version: dict[int, dict[str, ast.AST]],
    version_selection_strategy: str,
) -> list[ast.AST]:
    out: list[ast.AST] = []
    candidates: list[tuple[int, ast.AST]] = []
    for entry in sorted(entries, key=lambda item: item["version"]):
        version = entry["version"]
        source_name = entry["name"]
        node = top_level_by_version[version][source_name]
        impl_name = f"_mvo_{public_name}_v{version}_{source_name}"
        if entry["kind"] == "function":
            func_copy = copy.deepcopy(node)
            func_copy.name = impl_name
            out.append(func_copy)
            value = ast.Name(id=impl_name, ctx=ast.Load())
        elif entry["kind"] == "class":
            class_copy = copy.deepcopy(node)
            class_copy.name = impl_name
            out.append(class_copy)
            value = ast.Name(id=impl_name, ctx=ast.Load())
        else:
            value = _extract_assignment_value(node)
            if value is None:
                continue
        candidates.append((version, value))

    out.append(ast.Assign(
        targets=[ast.Name(id=public_name, ctx=ast.Store())],
        value=ast.Call(
            func=ast.Name(id="MVOAccess", ctx=ast.Load()),
            args=[
                ast.Dict(
                    keys=[ast.Constant(value=version) for version, _ in candidates],
                    values=[
                        ast.Dict(
                            keys=[ast.Constant(value="value")],
                            values=[value],
                        )
                        for _, value in candidates
                    ],
                )
            ],
            keywords=[ast.keyword(arg="strategy", value=ast.Constant(value=version_selection_strategy))],
        ),
    ))
    return out


def _extract_assignment_value(node: ast.AST | None) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        return copy.deepcopy(node.value)
    if isinstance(node, ast.AnnAssign):
        return copy.deepcopy(node.value)
    return None


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
