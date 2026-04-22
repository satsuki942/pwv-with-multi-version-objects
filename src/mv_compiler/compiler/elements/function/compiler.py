import ast
import copy

from ...common.util import logger
from ...common.util.constants import VERSION_SELECTION_LATEST
from ..signature import ParameterInfo, create_parameter_infos, create_signature_bind_check_call


def build_function_export(
    export_name: str,
    spec: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    versioned_value_names: set[str],
    version_selection_strategy: str,
) -> list[ast.AST]:
    impl_functions: dict[int, ast.FunctionDef] = {}
    parameter_infos_by_version: dict[int, list[ParameterInfo]] = {}
    for version in versions:
        source_name = spec.get("versions", {}).get(str(version), export_name)
        func_node = top_level_by_version[version].get(source_name)
        if not isinstance(func_node, ast.FunctionDef):
            logger.error_log(f"Function export not found: {export_name} v{version}")
            continue
        func_copy = copy.deepcopy(func_node)
        func_copy.name = _versioned_func_name(version, export_name)
        impl_functions[version] = func_copy
        parameter_infos_by_version[version] = create_parameter_infos(func_node)

    # 版ごとの実体関数は公開関数のローカル実装として閉じ込める。
    wrapper_body: list[ast.AST] = [impl_functions[version] for version in versions if version in impl_functions]
    wrapper_body.append(ast.Assign(
        targets=[ast.Name(id="current_version", ctx=ast.Store())],
        value=ast.Attribute(
            value=ast.Name(id=export_name, ctx=ast.Load()),
            attr="_mvo_current_version",
            ctx=ast.Load(),
        ),
    ))

    current_version_dispatch = _build_current_version_dispatch(
        export_name,
        versions,
        parameter_infos_by_version,
    )
    if current_version_dispatch:
        wrapper_body.append(current_version_dispatch)
    wrapper_body.extend(_build_signature_dispatcher(export_name, versions, parameter_infos_by_version))

    wrapper = ast.FunctionDef(
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
    )
    initial_version = versions[-1] if version_selection_strategy == VERSION_SELECTION_LATEST else versions[0]
    current_version_assign = ast.Assign(
        targets=[
            ast.Attribute(
                value=ast.Name(id=export_name, ctx=ast.Load()),
                attr="_mvo_current_version",
                ctx=ast.Store(),
            )
        ],
        value=ast.Constant(value=initial_version),
    )
    return [wrapper, current_version_assign]


def _versioned_func_name(version: int, export_name: str) -> str:
    return f"_v{version}_{export_name}"


def _build_local_versioned_function_call(version: int, export_name: str) -> ast.Call:
    return ast.Call(
        func=ast.Name(id=_versioned_func_name(version, export_name), ctx=ast.Load()),
        args=[ast.Starred(value=ast.Name(id="args", ctx=ast.Load()), ctx=ast.Load())],
        keywords=[ast.keyword(arg=None, value=ast.Name(id="kwargs", ctx=ast.Load()))],
    )

def _build_current_version_dispatch(
    export_name: str,
    versions: list[int],
    parameter_infos_by_version: dict[int, list[ParameterInfo]],
) -> ast.If | None:
    top_if_stmt: ast.If | None = None
    current_if_stmt: ast.If | None = None
    for version in versions:
        if version not in parameter_infos_by_version:
            continue
        condition = ast.BoolOp(op=ast.And(), values=[
            ast.Compare(
                left=ast.Name(id="current_version", ctx=ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=version)],
            ),
            create_signature_bind_check_call(ast.Name(id=_versioned_func_name(version, export_name), ctx=ast.Load())),
        ])
        if_stmt = ast.If(
            test=condition,
            body=[ast.Return(value=_build_local_versioned_function_call(version, export_name))],
            orelse=[],
        )
        if top_if_stmt is None:
            top_if_stmt = if_stmt
            current_if_stmt = if_stmt
        else:
            current_if_stmt.orelse = [if_stmt]
            current_if_stmt = if_stmt
    return top_if_stmt


def _build_signature_dispatcher(
    export_name: str,
    versions: list[int],
    parameter_infos_by_version: dict[int, list[ParameterInfo]],
) -> list[ast.AST]:
    top_if_stmt: ast.If | None = None
    current_if_stmt: ast.If | None = None
    for version in versions:
        if version not in parameter_infos_by_version:
            continue
        if_body = [
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id=export_name, ctx=ast.Load()),
                        attr="_mvo_current_version",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Constant(value=version),
            ),
            ast.Return(value=_build_local_versioned_function_call(version, export_name)),
        ]
        if_stmt = ast.If(
            test=create_signature_bind_check_call(ast.Name(id=_versioned_func_name(version, export_name), ctx=ast.Load())),
            body=if_body,
            orelse=[],
        )
        if top_if_stmt is None:
            top_if_stmt = if_stmt
            current_if_stmt = if_stmt
        else:
            current_if_stmt.orelse = [if_stmt]
            current_if_stmt = if_stmt

    if current_if_stmt:
        current_if_stmt.orelse = [ast.Raise(
            exc=ast.Call(
                func=ast.Name(id="TypeError", ctx=ast.Load()),
                args=[ast.Constant(value=f"No version of '{export_name}' matches the provided arguments.")],
                keywords=[],
            ),
            cause=None,
        )]

    return [top_if_stmt] if top_if_stmt else []
