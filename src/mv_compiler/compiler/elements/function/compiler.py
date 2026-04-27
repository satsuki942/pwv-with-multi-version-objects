import ast
import copy

from ...common.util import logger
from ..entity import entity_source_node
from ..signature import ParameterInfo, create_parameter_infos, create_signature_bind_check_call


def build_function_entity(
    entity_name: str,
    spec: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    version_selection_strategy: str,
) -> list[ast.AST]:
    """function entityを、引数形状でversion選択するラッパー関数ASTへ変換する。

    Args:
        entity_name: 生成後に公開される論理関数名。
        spec: 正規化済みentity spec。
        top_level_by_version: versionごとのトップレベル定義索引。
        versions: 当該モジュールで宣言されているversion一覧。
        version_selection_strategy: 実行時にversionを選ぶ戦略名。

    Returns:
        ラッパー関数定義と、現在versionを保持する属性代入AST。
    """
    impl_functions: dict[int, ast.FunctionDef] = {}
    parameter_infos_by_version: dict[int, list[ParameterInfo]] = {}
    for version in versions:
        func_node = entity_source_node(top_level_by_version, entity_name, spec, version)
        if not isinstance(func_node, ast.FunctionDef):
            logger.error_log(f"Function entity not found: {entity_name} v{version}")
            continue
        func_copy = copy.deepcopy(func_node)
        func_copy.name = _versioned_func_name(version, entity_name)
        impl_functions[version] = func_copy
        parameter_infos_by_version[version] = create_parameter_infos(func_node)

    # 版ごとの実体関数は公開関数のローカル実装として閉じ込める。
    wrapper_body: list[ast.AST] = [impl_functions[version] for version in versions if version in impl_functions]
    wrapper_body.append(ast.Assign(
        targets=[ast.Name(id="current_version", ctx=ast.Store())],
        value=ast.Attribute(
            value=ast.Name(id=entity_name, ctx=ast.Load()),
            attr="_mvo_current_version",
            ctx=ast.Load(),
        ),
    ))

    current_version_dispatch = _build_current_version_dispatch(
        entity_name,
        versions,
        parameter_infos_by_version,
    )
    if current_version_dispatch:
        wrapper_body.append(current_version_dispatch)
    wrapper_body.extend(_build_signature_dispatcher(entity_name, versions, parameter_infos_by_version))

    wrapper = ast.FunctionDef(
        name=entity_name,
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
    initial_version = versions[-1]
    current_version_assign = ast.Assign(
        targets=[
            ast.Attribute(
                value=ast.Name(id=entity_name, ctx=ast.Load()),
                attr="_mvo_current_version",
                ctx=ast.Store(),
            )
        ],
        value=ast.Constant(value=initial_version),
    )
    return [wrapper, current_version_assign]


def _versioned_func_name(version: int, entity_name: str) -> str:
    """ラッパー内部に閉じ込める版別実体関数名を作る。"""
    return f"_v{version}_{entity_name}"


def _build_local_versioned_function_call(version: int, entity_name: str) -> ast.Call:
    """版別実体関数へ、ラッパーが受けたargs/kwargsをそのまま渡す呼び出しを作る。"""
    return ast.Call(
        func=ast.Name(id=_versioned_func_name(version, entity_name), ctx=ast.Load()),
        args=[ast.Starred(value=ast.Name(id="args", ctx=ast.Load()), ctx=ast.Load())],
        keywords=[ast.keyword(arg=None, value=ast.Name(id="kwargs", ctx=ast.Load()))],
    )


def _build_current_version_dispatch(
    entity_name: str,
    versions: list[int],
    parameter_infos_by_version: dict[int, list[ParameterInfo]],
) -> ast.If | None:
    """現在versionの関数が呼び出し引数に適合するなら、そのversionを優先して呼ぶ分岐を作る。"""
    top_if_stmt: ast.If | None = None
    current_if_stmt: ast.If | None = None
    for version in sorted(versions, reverse=True):
        if version not in parameter_infos_by_version:
            continue
        condition = ast.BoolOp(op=ast.And(), values=[
            ast.Compare(
                left=ast.Name(id="current_version", ctx=ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=version)],
            ),
            create_signature_bind_check_call(ast.Name(id=_versioned_func_name(version, entity_name), ctx=ast.Load())),
        ])
        if_stmt = ast.If(
            test=condition,
            body=[ast.Return(value=_build_local_versioned_function_call(version, entity_name))],
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
    entity_name: str,
    versions: list[int],
    parameter_infos_by_version: dict[int, list[ParameterInfo]],
) -> list[ast.AST]:
    """引数形状に適合するversionを探し、見つかったversionへ切り替えて呼ぶ分岐列を作る。"""
    top_if_stmt: ast.If | None = None
    current_if_stmt: ast.If | None = None
    for version in versions:
        if version not in parameter_infos_by_version:
            continue
        if_body = [
            ast.Assign(
                targets=[
                    ast.Attribute(
                        value=ast.Name(id=entity_name, ctx=ast.Load()),
                        attr="_mvo_current_version",
                        ctx=ast.Store(),
                    )
                ],
                value=ast.Constant(value=version),
            ),
            ast.Return(value=_build_local_versioned_function_call(version, entity_name)),
        ]
        if_stmt = ast.If(
            test=create_signature_bind_check_call(ast.Name(id=_versioned_func_name(version, entity_name), ctx=ast.Load())),
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
                args=[ast.Constant(value=f"No version of '{entity_name}' matches the provided arguments.")],
                keywords=[],
            ),
            cause=None,
        )]

    return [top_if_stmt] if top_if_stmt else []
