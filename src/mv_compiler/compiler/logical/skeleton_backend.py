import ast
import copy

from .ir import (
    FunctionRealizationIR,
    LogicalFunctionIR,
    LogicalModuleIR,
    LogicalObjectIR,
    LogicalObjectKind,
)


def emit_logical_module_skeleton(module_ir: LogicalModuleIR) -> ast.Module:
    """
    LogicalModuleIR から実行可能な Python モジュールの最小スケルトンを生成する。

    compatibility.functions がある関数はhidden実体と公開ラッパーへ変換する。
    それ以外の関数とクラス・変数は、まだ最小スケルトンとして出力する。
    """
    body: list[ast.AST] = [
        copy.deepcopy(import_node)
        for import_node in module_ir.import_nodes
    ]
    for obj in module_ir.objects:
        emitted = _emit_logical_object(obj)
        body.extend(emitted)

    # 空モジュールは Python AST として不自然にならないよう pass を出す。
    if not body:
        body.append(ast.Pass())

    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    return module


def _emit_logical_object(obj: LogicalObjectIR) -> list[ast.AST]:
    """論理要素の種類に応じてスケルトンASTを生成する。"""
    if obj.kind == LogicalObjectKind.IMPORT:
        return []
    if obj.kind == LogicalObjectKind.FUNCTION:
        return _emit_function(obj)
    if obj.kind == LogicalObjectKind.CLASS:
        return [_emit_class(obj)]
    if obj.kind == LogicalObjectKind.VARIABLE:
        return [_emit_variable(obj)]
    return []


def _emit_function(obj: LogicalObjectIR) -> list[ast.AST]:
    """公開シグネチャだけを保った関数スケルトンを生成する。"""
    if obj.function_ir is not None:
        return _emit_logical_function(obj.function_ir)

    node = obj.base_version_node
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(f"Logical function object has invalid AST node: {obj.public_name}")

    # 呼び出し形は保ちつつ、実装本体は後続の論理操作生成フェーズに委ねる。
    new_node = copy.deepcopy(node)
    new_node.decorator_list = []
    new_node.body = [_not_implemented_raise("function", obj.public_name)]
    return [new_node]


def _emit_logical_function(function_ir: LogicalFunctionIR) -> list[ast.AST]:
    """論理関数IRから、版別hidden実装と公開ラッパーを生成する。"""
    hidden_functions = [
        _emit_hidden_function(function_ir, version)
        for version in sorted(function_ir.sources)
    ]
    wrapper = _emit_function_wrapper(function_ir)
    return [*hidden_functions, wrapper]


def _emit_hidden_function(function_ir: LogicalFunctionIR, version: int) -> ast.FunctionDef:
    """元関数をコピーし、_v{version}_{entity} というhidden実装名へ変更する。"""
    source = function_ir.sources[version]
    hidden = copy.deepcopy(source.node)
    hidden.name = _hidden_function_name(function_ir.entity, version)
    return hidden


def _emit_function_wrapper(function_ir: LogicalFunctionIR) -> ast.FunctionDef:
    """公開論理関数からfixed meaningのcall realizationへ委譲するラッパーを作る。"""
    fixed_meaning = function_ir.meaning_resolution.meaning
    realization = _select_fixed_realization(function_ir, fixed_meaning)
    wrapper_body: list[ast.AST] = [
        _docstring_expr(_build_function_spec_docstring(function_ir)),
        ast.Assign(
            targets=[ast.Name(id="_mvo_meaning", ctx=ast.Store())],
            value=ast.Constant(value=fixed_meaning),
        ),
        ast.If(
            test=ast.Compare(
                left=ast.Name(id="_mvo_meaning", ctx=ast.Load()),
                ops=[ast.Eq()],
                comparators=[ast.Constant(value=fixed_meaning)],
            ),
            body=[
                ast.Return(value=_call_hidden_function(function_ir, realization))
            ],
            orelse=[],
        ),
        ast.Raise(
            exc=ast.Call(
                func=ast.Name(id="RuntimeError", ctx=ast.Load()),
                args=[ast.Constant(value=f"No realization selected for logical function '{function_ir.entity}'.")],
                keywords=[],
            ),
            cause=None,
        ),
    ]
    return ast.FunctionDef(
        name=function_ir.public_name,
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


def _build_function_spec_docstring(function_ir: LogicalFunctionIR) -> str:
    """生成後の論理関数に埋め込む、互換仕様の短い要約を作る。"""
    lines = [
        "呼び出し解釈:",
        f"- fixed: {function_ir.meaning_resolution.meaning}",
        "実行候補:",
    ]
    for realization in function_ir.realizations:
        implementation = realization.implementation
        lines.extend([
            (
                f"- {realization.meaning}: {implementation.kind} "
                f"v{implementation.version}.{implementation.name} "
                f"-> {_hidden_function_name(function_ir.entity, implementation.version)}"
            ),
            f"  前提条件: {_brief_list(realization.preconditions)}",
            f"  事前調整: {_brief_list(realization.pre_adjustments)}",
        ])
    return "\n".join(lines)


def _docstring_expr(value: str) -> ast.Expr:
    """AST関数本体の先頭に置くdocstringノードを作る。"""
    return ast.Expr(value=ast.Constant(value=value))


def _brief_list(items: list[object]) -> str:
    """仕様要約で使う短いリスト表示を作る。"""
    return "なし" if not items else f"{len(items)}件"


def _select_fixed_realization(function_ir: LogicalFunctionIR, meaning: str) -> FunctionRealizationIR:
    """fixed meaningに対応する最初のrealizationを選ぶ。"""
    for realization in function_ir.realizations:
        if realization.meaning == meaning:
            return realization
    raise ValueError(f"Logical function {function_ir.entity} has no realization for meaning: {meaning}")


def _call_hidden_function(function_ir: LogicalFunctionIR, realization: FunctionRealizationIR) -> ast.Call:
    """ラッパーが受け取ったargs/kwargsをhidden実装へそのまま渡す呼び出しを作る。"""
    implementation = realization.implementation
    return ast.Call(
        func=ast.Name(
            id=_hidden_function_name(function_ir.entity, implementation.version),
            ctx=ast.Load(),
        ),
        args=[ast.Starred(value=ast.Name(id="args", ctx=ast.Load()), ctx=ast.Load())],
        keywords=[ast.keyword(arg=None, value=ast.Name(id="kwargs", ctx=ast.Load()))],
    )


def _hidden_function_name(entity: str, version: int) -> str:
    """版別hidden実装の関数名を作る。"""
    return f"_v{version}_{entity}"


def _emit_class(obj: LogicalObjectIR) -> ast.ClassDef:
    """クラス名だけを公開する空クラススケルトンを生成する。"""
    node = obj.base_version_node
    if not isinstance(node, ast.ClassDef):
        raise ValueError(f"Logical class object has invalid AST node: {obj.public_name}")

    return ast.ClassDef(
        name=node.name,
        bases=[],
        keywords=[],
        body=[ast.Pass()],
        decorator_list=[],
    )


def _emit_variable(obj: LogicalObjectIR) -> ast.Assign:
    """トップレベル変数の公開名を保持する仮代入を生成する。"""
    if not obj.public_name:
        raise ValueError("Logical variable object must have a public name")
    return ast.Assign(
        targets=[ast.Name(id=obj.public_name, ctx=ast.Store())],
        value=ast.Constant(value=None),
    )


def _not_implemented_raise(kind: str, public_name: str | None) -> ast.Raise:
    """未実装の論理要素が呼ばれたことを示す raise ノードを作る。"""
    name = public_name or "<anonymous>"
    return ast.Raise(
        exc=ast.Call(
            func=ast.Name(id="NotImplementedError", ctx=ast.Load()),
            args=[ast.Constant(value=f"Logical {kind} '{name}' is not implemented yet.")],
            keywords=[],
        ),
        cause=None,
    )
