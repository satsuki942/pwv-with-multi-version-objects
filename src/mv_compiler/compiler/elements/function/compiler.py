import ast
import copy

from ...common.util import logger
from ...common.util.constants import VERSION_SELECTION_LATEST
from ..class_.builder_util import _create_signature_check_condition
from ..class_.symbol_table.method_info import ParameterInfo


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
        parameter_infos_by_version[version] = _create_parameter_infos(func_node)

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


def _create_parameter_infos(function_node: ast.FunctionDef) -> list[ParameterInfo]:
    parameters: list[ParameterInfo] = []
    args = function_node.args
    pos_args = args.posonlyargs + args.args
    defaults_start_index = len(pos_args) - len(args.defaults)

    for i, arg in enumerate(args.posonlyargs):
        parameters.append(ParameterInfo(
            name=arg.arg,
            type=ast.unparse(arg.annotation) if arg.annotation else "any",
            has_default_value=(i >= defaults_start_index),
            kind="POSITIONAL_ONLY",
        ))

    for i, arg in enumerate(args.args):
        combined_index = len(args.posonlyargs) + i
        parameters.append(ParameterInfo(
            name=arg.arg,
            type=ast.unparse(arg.annotation) if arg.annotation else "any",
            has_default_value=(combined_index >= defaults_start_index),
            kind="POSITIONAL_OR_KEYWORD",
        ))

    if args.vararg:
        parameters.append(ParameterInfo(
            name=args.vararg.arg,
            type=ast.unparse(args.vararg.annotation) if args.vararg.annotation else "any",
            has_default_value=False,
            kind="VAR_POSITIONAL",
        ))

    for i, arg in enumerate(args.kwonlyargs):
        parameters.append(ParameterInfo(
            name=arg.arg,
            type=ast.unparse(arg.annotation) if arg.annotation else "any",
            has_default_value=args.kw_defaults[i] is not None,
            kind="KEYWORD_ONLY",
        ))

    if args.kwarg:
        parameters.append(ParameterInfo(
            name=args.kwarg.arg,
            type=ast.unparse(args.kwarg.annotation) if args.kwarg.annotation else "any",
            has_default_value=False,
            kind="VAR_KEYWORD",
        ))

    return parameters


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
            _create_signature_check_condition(parameter_infos_by_version[version]),
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
            test=_create_signature_check_condition(parameter_infos_by_version[version]),
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
