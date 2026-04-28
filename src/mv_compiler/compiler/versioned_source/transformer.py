from __future__ import annotations

import ast
import copy
from pathlib import Path

from ..common.util.constants import DEFAULT_VERSION_SELECTION_STRATEGY
from ..elements.class_.compiler import build_unified_classes_for_module
from ..elements.function.compiler import build_function_entity
from ..elements.signature import build_signature_runtime_support
from ..elements.variable.compiler import build_module_runtime, build_variable_entity
from .syntax import parse_versioned_operation
from .model import EntityHistory, ParsedModule
from .parser import parse_versioned_source_module


def transform_versioned_source_module(
    rel_path: Path,
    tree: ast.Module,
    *,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
) -> tuple[Path, ast.Module]:
    """DSL付き単一モジュールを実行可能な Python AST へ変換する。"""
    parsed = parse_versioned_source_module(rel_path, tree)
    new_body: list[ast.AST] = []

    # import はソース上の位置に関係なく、実行前提として先頭へ集約する。
    new_body.extend(_dedupe_imports(parsed.imports))

    if _needs_signature_runtime(parsed):
        new_body.extend(build_signature_runtime_support())
    if _needs_variable_runtime(parsed):
        new_body.extend(build_module_runtime(version_selection_strategy, parsed.max_version))

    generated_by_order = {entity.order: _build_entity_nodes(entity, version_selection_strategy) for entity in parsed.entities}
    normal_by_order = {statement.order: [copy.deepcopy(statement.node)] for statement in parsed.normal_statements}

    # entity と通常文は、import/runtime を除いて元の top-level 順へ戻す。
    for order in sorted({*generated_by_order.keys(), *normal_by_order.keys()}):
        new_body.extend(generated_by_order.get(order, []))
        new_body.extend(normal_by_order.get(order, []))

    module = ast.Module(body=new_body, type_ignores=[])
    ast.fix_missing_locations(module)
    return rel_path, module


def _build_entity_nodes(entity: EntityHistory, version_selection_strategy: str) -> list[ast.AST]:
    if len(entity.versions) == 1:
        return [_single_definition_node(entity)]

    top_level_by_version = _build_top_level_by_version(entity)
    versions = entity.concrete_versions()
    spec = _entity_spec(entity)
    sync_functions = _sync_function_map(entity)

    if entity.kind == "class":
        return build_unified_classes_for_module(
            {entity.entity_key: spec},
            top_level_by_version,
            versions,
            sync_functions,
            {},
            version_selection_strategy,
        ) + _alias_assignments(entity)

    if entity.kind == "function":
        return build_function_entity(
            entity.entity_key,
            spec,
            top_level_by_version,
            versions,
            version_selection_strategy,
        ) + _alias_assignments(entity)

    variable_node = build_variable_entity(
        entity.entity_key,
        spec,
        top_level_by_version,
        versions,
        versions[-1],
        version_selection_strategy,
    )
    return ([variable_node] if variable_node else []) + _alias_assignments(entity)


def _single_definition_node(entity: EntityHistory) -> ast.AST:
    version = entity.latest_version()
    return copy.deepcopy(version.node)


def _build_top_level_by_version(entity: EntityHistory) -> dict[int, dict[str, ast.AST]]:
    by_version: dict[int, dict[str, ast.AST]] = {}
    for version in entity.versions:
        by_version.setdefault(version.version, {})[version.name] = version.node
    return by_version


def _entity_spec(entity: EntityHistory) -> dict:
    source_names = {str(version.version): version.name for version in entity.versions}
    spec = {
        "kind": entity.kind,
        "entity_key": entity.entity_key,
        "entity_name": entity.entity_key,
        "source_names": source_names,
        "aliases": [name for name in entity.public_names() if name != entity.entity_key],
        "sync_key": entity.entity_key,
    }
    if entity.kind == "variable":
        spec["versioned_by"] = entity.variable_versioning
    return spec


def _sync_function_map(entity: EntityHistory) -> dict:
    sync_functions: list[ast.FunctionDef] = []
    for version in entity.versions:
        sync_functions.extend(copy.deepcopy(version.sync_functions))
    return {entity.entity_key: ([], sync_functions)}


def _alias_assignments(entity: EntityHistory) -> list[ast.Assign]:
    assignments: list[ast.Assign] = []
    for alias in entity.public_names():
        if alias == entity.entity_key:
            continue
        assignments.append(ast.Assign(
            targets=[ast.Name(id=alias, ctx=ast.Store())],
            value=ast.Name(id=entity.entity_key, ctx=ast.Load()),
        ))
    return assignments


def _dedupe_imports(import_nodes: list[ast.AST]) -> list[ast.AST]:
    imports: dict[str, ast.AST] = {}
    for import_node in import_nodes:
        imports.setdefault(ast.unparse(import_node), import_node)
    return list(imports.values())


def _needs_signature_runtime(parsed: ParsedModule) -> bool:
    return any(entity.kind in {"class", "function"} and len(entity.versions) > 1 for entity in parsed.entities)


def _needs_variable_runtime(parsed: ParsedModule) -> bool:
    return any(
        entity.kind == "variable"
        and len(entity.versions) > 1
        and entity.variable_versioning == "generated"
        for entity in parsed.entities
    )


def has_versioned_source_syntax(tree: ast.Module) -> bool:
    """入力ASTが versioned source DSL を含むかどうかを判定するための軽量検出。"""
    for node in tree.body:
        if isinstance(node, ast.With):
            if parse_versioned_operation(node) is not None:
                return True
    return False
