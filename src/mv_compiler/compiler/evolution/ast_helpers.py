from __future__ import annotations

import ast


DSL_ROOT_NAME = "_mv"


def is_import_node(node: ast.AST) -> bool:
    return isinstance(node, (ast.Import, ast.ImportFrom))


def top_level_entity_kind(node: ast.AST) -> str | None:
    """top-level 文が DSL 対象 entity なら kind を返す。"""
    if isinstance(node, ast.ClassDef):
        return "class"
    if isinstance(node, ast.FunctionDef):
        return "function"
    if is_variable_definition(node):
        return "variable"
    return None


def entity_name(node: ast.AST) -> str:
    """対応済み entity node から公開名を取り出す。"""
    if isinstance(node, (ast.ClassDef, ast.FunctionDef)):
        return node.name
    if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
        return node.targets[0].id
    if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
        return node.target.id
    raise ValueError(f"Unsupported entity node: {type(node).__name__}")


def is_variable_definition(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    ) or (
        isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
    )


def unwrap_mv_var(node: ast.AST) -> tuple[ast.AST, str | None]:
    """`_mv.var(value, variable_versioning=...)` を通常代入へ戻す。"""
    if isinstance(node, ast.Assign):
        call = node.value
    elif isinstance(node, ast.AnnAssign):
        call = node.value
    else:
        return node, None

    if not isinstance(call, ast.Call) or not _is_mv_attr_call(call.func, "var"):
        return node, None
    if not call.args:
        raise ValueError("_mv.var() requires an initial value")

    variable_versioning = None
    for keyword in call.keywords:
        if keyword.arg == "variable_versioning" and isinstance(keyword.value, ast.Constant):
            variable_versioning = keyword.value.value
    if variable_versioning not in {"generated", "referenced"}:
        raise ValueError("_mv.var() requires variable_versioning='generated' or 'referenced'")

    new_node = ast.copy_location(ast.fix_missing_locations(ast.parse("_x = None").body[0]), node)
    if isinstance(node, ast.Assign):
        new_node = ast.Assign(targets=node.targets, value=call.args[0])
    else:
        new_node = ast.AnnAssign(target=node.target, annotation=node.annotation, value=call.args[0], simple=node.simple)
    return ast.copy_location(new_node, node), variable_versioning


def parse_versioned_operation(node: ast.AST) -> tuple[int, str, list[ast.expr], list[ast.keyword]] | None:
    """`with _mv.v(N).op(...):` なら version と operation を返す。"""
    if not isinstance(node, ast.With) or len(node.items) != 1:
        return None
    context_expr = node.items[0].context_expr
    if not isinstance(context_expr, ast.Call):
        return None
    op_func = context_expr.func
    if not isinstance(op_func, ast.Attribute):
        return None
    version_call = op_func.value
    if not isinstance(version_call, ast.Call) or not _is_mv_attr_call(version_call.func, "v"):
        return None
    if len(version_call.args) != 1 or not isinstance(version_call.args[0], ast.Constant):
        raise ValueError("_mv.v(...) requires a single integer version")
    version = version_call.args[0].value
    if not isinstance(version, int) or isinstance(version, bool):
        raise ValueError("_mv.v(...) requires a single integer version")
    return version, op_func.attr, context_expr.args, context_expr.keywords


def contains_versioned_operation(node: ast.AST) -> bool:
    for child in ast.walk(node):
        if child is node:
            continue
        if parse_versioned_operation(child) is not None:
            return True
    return False


def _is_mv_attr_call(func: ast.expr, attr: str) -> bool:
    return (
        isinstance(func, ast.Attribute)
        and func.attr == attr
        and isinstance(func.value, ast.Name)
        and func.value.id == DSL_ROOT_NAME
    )

