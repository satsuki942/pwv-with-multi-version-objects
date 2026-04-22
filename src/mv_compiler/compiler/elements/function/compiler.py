import ast
import copy

from ...common.util import logger
from ...common.util.constants import VERSION_SELECTION_LATEST
from ..variable.reference_rewriter import VersionedValueNameRewriter


def build_function_export(
    export_name: str,
    spec: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    versioned_value_names: set[str],
    version_selection_strategy: str,
) -> list[ast.AST]:
    impl_functions: list[ast.FunctionDef] = []
    for version in versions:
        source_name = spec.get("versions", {}).get(str(version), export_name)
        func_node = top_level_by_version[version].get(source_name)
        if not isinstance(func_node, ast.FunctionDef):
            logger.error_log(f"Function export not found: {export_name} v{version}")
            continue
        func_copy = copy.deepcopy(func_node)
        func_copy.name = _versioned_func_name(version, export_name)
        func_copy = VersionedValueNameRewriter(versioned_value_names, version).visit(func_copy)
        impl_functions.append(func_copy)

    latest_version = versions[-1]
    version_value: ast.AST
    if version_selection_strategy == VERSION_SELECTION_LATEST:
        version_value = ast.Constant(value=latest_version)
    else:
        version_value = ast.Name(id="_MVO_CURRENT_VERSION", ctx=ast.Load())

    # 版ごとの実体関数は公開関数のローカル実装として閉じ込める。
    wrapper_body: list[ast.AST] = [*impl_functions]
    wrapper_body.append(ast.Assign(
        targets=[ast.Name(id="version", ctx=ast.Store())],
        value=ast.Call(
            func=ast.Name(id="_mvo_set_module_version", ctx=ast.Load()),
            args=[version_value],
            keywords=[],
        ),
    ))
    wrapper_body.append(ast.If(
        test=ast.Compare(
            left=ast.Name(id="version", ctx=ast.Load()),
            ops=[ast.Eq()],
            comparators=[ast.Constant(value=versions[0])],
        ),
        body=[ast.Return(value=_build_local_versioned_function_call(versions[0], export_name))],
        orelse=[ast.Return(value=_build_local_versioned_function_call(versions[-1], export_name))],
    ))

    return [ast.FunctionDef(
        name=export_name,
        args=ast.arguments(
            posonlyargs=[],
            args=[],
            vararg=ast.arg(arg="args"),
            kwonlyargs=[],
            kw_defaults=[],
            kwarg=ast.arg(arg="kwargs"),
            defaults=[],
        ),
        body=wrapper_body,
        decorator_list=[],
    )]


def _versioned_func_name(version: int, export_name: str) -> str:
    return f"_v{version}_{export_name}"


def _build_local_versioned_function_call(version: int, export_name: str) -> ast.Call:
    return ast.Call(
        func=ast.Name(id=_versioned_func_name(version, export_name), ctx=ast.Load()),
        args=[ast.Starred(value=ast.Name(id="args", ctx=ast.Load()), ctx=ast.Load())],
        keywords=[ast.keyword(arg=None, value=ast.Name(id="kwargs", ctx=ast.Load()))],
    )
