from __future__ import annotations

import ast
from pathlib import Path

from .syntax import (
    contains_versioned_operation,
    entity_name,
    is_import_node,
    parse_versioned_operation,
    top_level_entity_kind,
)
from .model import EntityHistory, EntityVersion, NormalStatement, ParsedModule


ENTITY_OPS = {"change", "rename", "add", "delete", "revive"}
ALL_OPS = {"imports", *ENTITY_OPS}
VARIABLE_VERSIONING_OPS = {"change", "rename", "revive"}


def parse_versioned_source_module(rel_path: Path, tree: ast.Module) -> ParsedModule:
    """top-level versioned source DSL を中間表現へ変換する。"""
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
                raise ValueError(f"Unknown versioned source DSL operation: {op}")
            if contains_versioned_operation_in_body(node):
                raise ValueError("Versioned source DSL blocks are only supported at module top-level")

            if op == "imports":
                _validate_operation_arguments(op, args, keywords)
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
            raise ValueError("Versioned source DSL blocks are only supported at module top-level")

        if is_import_node(node):
            imports.append(node)
            current_entity = None
            continue

        kind = top_level_entity_kind(node)
        if kind:
            history = EntityHistory(
                entity_key=entity_name(node),
                kind=kind,  # type: ignore[arg-type]
                order=order,
                versions=[EntityVersion(version=1, name=entity_name(node), node=node)],
            )
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
    _validate_operation_arguments(op, args, keywords)

    if op == "add":
        entity_node, sync_functions = _single_entity_from_block(node)
        kind = top_level_entity_kind(entity_node)
        history = EntityHistory(
            entity_key=entity_name(entity_node),
            kind=kind,  # type: ignore[arg-type]
            order=order,
            versions=[EntityVersion(version=version, name=entity_name(entity_node), node=entity_node, sync_functions=sync_functions)],
        )
        entities.append(history)
        return history

    if current_entity is None:
        raise ValueError(f"_mv.v(...).{op}() must follow an entity definition")

    if op == "delete":
        _validate_delete_block(node, current_entity)
        current_entity.deleted_at.append(version)
        return current_entity

    entity_node, sync_functions = _single_entity_from_block(node)
    variable_versioning = _keyword_string(keywords, "variable_versioning")
    kind = top_level_entity_kind(entity_node)
    if kind != current_entity.kind:
        raise ValueError(f"{op}() must keep the same entity kind")
    if variable_versioning and kind != "variable":
        raise ValueError("variable_versioning is allowed only for variable history blocks")
    if kind == "variable" and current_entity.variable_versioning is None and variable_versioning is None:
        raise ValueError("Variable versioned source block requires variable_versioning='generated' or 'referenced'")
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


def _validate_operation_arguments(op: str, args: list[ast.expr], keywords: list[ast.keyword]) -> None:
    """operation ごとに受け取れる引数を先に絞る。"""
    if op == "rename":
        if _unexpected_keywords(keywords, {"variable_versioning"}):
            raise ValueError("rename() accepts only variable_versioning keyword")
        return

    if args:
        raise ValueError(f"{op}() does not accept positional arguments")

    if op in VARIABLE_VERSIONING_OPS:
        if _unexpected_keywords(keywords, {"variable_versioning"}):
            raise ValueError(f"{op}() accepts only variable_versioning keyword")
        return

    if keywords:
        raise ValueError(f"{op}() does not accept keyword arguments")


def _single_entity_from_block(
    node: ast.With,
) -> tuple[ast.AST, list[ast.FunctionDef]]:
    sync_functions = [statement for statement in node.body if _is_sync_function(statement)]
    entity_nodes = [statement for statement in node.body if not _is_sync_function(statement)]
    if len(entity_nodes) != 1:
        raise ValueError("Entity versioned source block must contain exactly one entity definition")

    entity_node = entity_nodes[0]
    if top_level_entity_kind(entity_node) is None:
        raise ValueError("Entity versioned source block must contain a variable, function, or class definition")
    if sync_functions and not isinstance(entity_node, ast.ClassDef):
        raise ValueError("Sync functions are allowed only inside class versioned source blocks")
    return entity_node, sync_functions


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


def _keyword_string(keywords: list[ast.keyword], name: str) -> str | None:
    """差分ブロック引数から文字列メタ情報を取り出す。"""
    for keyword in keywords:
        if keyword.arg != name:
            continue
        if not isinstance(keyword.value, ast.Constant) or not isinstance(keyword.value.value, str):
            raise ValueError(f"{name} must be a string literal")
        if name == "variable_versioning" and keyword.value.value not in {"generated", "referenced"}:
            raise ValueError("variable_versioning must be 'generated' or 'referenced'")
        return keyword.value.value
    return None


def _unexpected_keywords(keywords: list[ast.keyword], allowed: set[str]) -> list[str | None]:
    """許可されていないキーワード引数名を返す。"""
    return [keyword.arg for keyword in keywords if keyword.arg not in allowed]


def _is_sync_function(node: ast.AST) -> bool:
    if not isinstance(node, ast.FunctionDef):
        return False
    return node.name.startswith("_sync_from_v") or node.name.startswith("sync_from_v")

