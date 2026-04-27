from __future__ import annotations

import ast
from pathlib import Path

from .ast_helpers import (
    contains_versioned_operation,
    entity_name,
    is_import_node,
    parse_versioned_operation,
    top_level_entity_kind,
    unwrap_mv_var,
)
from .model import EntityHistory, EntityVersion, NormalStatement, ParsedModule


ENTITY_OPS = {"change", "rename", "add", "delete", "revive"}
ALL_OPS = {"imports", *ENTITY_OPS}


def parse_evolution_module(rel_path: Path, tree: ast.Module) -> ParsedModule:
    """top-level evolution DSL を中間表現へ変換する。"""
    imports: list[ast.AST] = []
    entities: list[EntityHistory] = []
    normal_statements: list[NormalStatement] = []
    current_entity: EntityHistory | None = None
    max_version = 1

    for order, node in enumerate(tree.body):
        operation = parse_versioned_operation(node)
        if operation:
            version, op, args, keywords = operation
            max_version = max(max_version, version)
            if op not in ALL_OPS:
                raise ValueError(f"Unknown evolution DSL operation: {op}")
            if contains_versioned_operation_in_body(node):
                raise ValueError("Evolution DSL blocks are only supported at module top-level")

            if op == "imports":
                imports.extend(_parse_import_block(node))
                continue

            current_entity = _apply_entity_operation(
                current_entity,
                entities,
                order,
                node,
                version,
                op,
                args,
                keywords,
            )
            continue

        if contains_versioned_operation(node):
            raise ValueError("Evolution DSL blocks are only supported at module top-level")

        if is_import_node(node):
            imports.append(node)
            current_entity = None
            continue

        entity_node, variable_versioning = unwrap_mv_var(node)
        kind = top_level_entity_kind(entity_node)
        if kind:
            history = EntityHistory(
                entity_key=entity_name(entity_node),
                kind=kind,  # type: ignore[arg-type]
                order=order,
                variable_versioning=variable_versioning,
                versions=[EntityVersion(version=1, name=entity_name(entity_node), node=entity_node)],
            )
            if kind == "variable" and variable_versioning is None:
                raise ValueError("Variable entity base definition must use _mv.var(..., variable_versioning=...)")
            entities.append(history)
            current_entity = history
            continue

        normal_statements.append(NormalStatement(order=order, node=node))
        current_entity = None

    return ParsedModule(
        rel_path=rel_path,
        imports=imports,
        entities=entities,
        normal_statements=normal_statements,
        max_version=max_version,
    )


def contains_versioned_operation_in_body(node: ast.With) -> bool:
    return any(contains_versioned_operation(statement) for statement in node.body)


def _parse_import_block(node: ast.With) -> list[ast.AST]:
    if not node.body or not all(is_import_node(statement) for statement in node.body):
        raise ValueError("_mv.v(...).imports() may contain only import statements")
    return list(node.body)


def _apply_entity_operation(
    current_entity: EntityHistory | None,
    entities: list[EntityHistory],
    order: int,
    node: ast.With,
    version: int,
    op: str,
    args: list[ast.expr],
    keywords: list[ast.keyword],
) -> EntityHistory:
    if op == "add":
        entity_node, variable_versioning, sync_functions = _single_entity_from_block(node, require_var_marker=True)
        kind = top_level_entity_kind(entity_node)
        history = EntityHistory(
            entity_key=entity_name(entity_node),
            kind=kind,  # type: ignore[arg-type]
            order=order,
            variable_versioning=variable_versioning,
            versions=[EntityVersion(version=version, name=entity_name(entity_node), node=entity_node, sync_functions=sync_functions)],
        )
        if kind == "variable" and variable_versioning is None:
            raise ValueError("Variable add() definition must use _mv.var(..., variable_versioning=...)")
        entities.append(history)
        return history

    if current_entity is None:
        raise ValueError(f"_mv.v(...).{op}() must follow an entity definition")

    if op == "delete":
        _validate_delete_block(node, current_entity)
        current_entity.deleted_at.append(version)
        return current_entity

    entity_node, variable_versioning, sync_functions = _single_entity_from_block(node, require_var_marker=False)
    kind = top_level_entity_kind(entity_node)
    if kind != current_entity.kind:
        raise ValueError(f"{op}() must keep the same entity kind")
    if variable_versioning and current_entity.variable_versioning and variable_versioning != current_entity.variable_versioning:
        raise ValueError("Variable versioning cannot change across an entity history")
    if variable_versioning and not current_entity.variable_versioning:
        current_entity.variable_versioning = variable_versioning

    name = entity_name(entity_node)
    if op == "rename":
        new_name = _single_string_arg(args, "rename")
        if name != new_name:
            raise ValueError("rename() argument must match the definition name")
    elif args:
        raise ValueError(f"{op}() does not accept positional arguments")

    current_entity.versions.append(EntityVersion(version=version, name=name, node=entity_node, sync_functions=sync_functions))
    return current_entity


def _single_entity_from_block(
    node: ast.With,
    *,
    require_var_marker: bool,
) -> tuple[ast.AST, str | None, list[ast.FunctionDef]]:
    sync_functions = [statement for statement in node.body if _is_sync_function(statement)]
    entity_nodes = [statement for statement in node.body if not _is_sync_function(statement)]
    if len(entity_nodes) != 1:
        raise ValueError("Entity evolution block must contain exactly one entity definition")

    entity_node, variable_versioning = unwrap_mv_var(entity_nodes[0])
    if top_level_entity_kind(entity_node) is None:
        raise ValueError("Entity evolution block must contain a variable, function, or class definition")
    if require_var_marker and top_level_entity_kind(entity_node) == "variable" and variable_versioning is None:
        raise ValueError("Added variable entity must use _mv.var(..., variable_versioning=...)")
    if sync_functions and not isinstance(entity_node, ast.ClassDef):
        raise ValueError("Sync functions are allowed only inside class evolution blocks")
    return entity_node, variable_versioning, sync_functions


def _validate_delete_block(node: ast.With, current_entity: EntityHistory) -> None:
    if len(node.body) != 1 or not isinstance(node.body[0], ast.Delete) or len(node.body[0].targets) != 1:
        raise ValueError("delete() block must contain exactly one 'del <name>' statement")
    target = node.body[0].targets[0]
    if not isinstance(target, ast.Name):
        raise ValueError("delete() block target must be a simple name")
    if target.id not in current_entity.public_names():
        raise ValueError("delete() target must be one of the entity public names")


def _single_string_arg(args: list[ast.expr], op: str) -> str:
    if len(args) != 1 or not isinstance(args[0], ast.Constant) or not isinstance(args[0].value, str):
        raise ValueError(f"{op}() requires a single string argument")
    return args[0].value


def _is_sync_function(node: ast.AST) -> bool:
    if not isinstance(node, ast.FunctionDef):
        return False
    return node.name.startswith("_sync_from_v") or node.name.startswith("sync_from_v")

