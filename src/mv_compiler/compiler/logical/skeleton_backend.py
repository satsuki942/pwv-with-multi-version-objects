import ast
import copy

from .ir import LogicalModuleIR, LogicalObjectIR, LogicalObjectKind


def emit_logical_module_skeleton(module_ir: LogicalModuleIR) -> ast.Module:
    """
    LogicalModuleIR から実行可能な Python モジュールの最小スケルトンを生成する。

    このバックエンドは論理操作の本体実装をまだ生成しない。公開形だけを保ち、
    関数は NotImplementedError、クラスは空クラスとして出力する。
    """
    body: list[ast.AST] = []
    for obj in module_ir.objects:
        emitted = _emit_logical_object(obj)
        if emitted is not None:
            body.append(emitted)

    # 空モジュールは Python AST として不自然にならないよう pass を出す。
    if not body:
        body.append(ast.Pass())

    module = ast.Module(body=body, type_ignores=[])
    ast.fix_missing_locations(module)
    return module


def _emit_logical_object(obj: LogicalObjectIR) -> ast.AST | None:
    """論理要素の種類に応じてスケルトンASTを生成する。"""
    if obj.kind == LogicalObjectKind.IMPORT:
        return copy.deepcopy(obj.base_version_node)
    if obj.kind == LogicalObjectKind.FUNCTION:
        return _emit_function(obj)
    if obj.kind == LogicalObjectKind.CLASS:
        return _emit_class(obj)
    if obj.kind == LogicalObjectKind.VARIABLE:
        return _emit_variable(obj)
    return None


def _emit_function(obj: LogicalObjectIR) -> ast.FunctionDef | ast.AsyncFunctionDef:
    """公開シグネチャだけを保った関数スケルトンを生成する。"""
    node = obj.base_version_node
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        raise ValueError(f"Logical function object has invalid AST node: {obj.public_name}")

    # 呼び出し形は保ちつつ、実装本体は後続の論理操作生成フェーズに委ねる。
    new_node = copy.deepcopy(node)
    new_node.decorator_list = []
    new_node.body = [_not_implemented_raise("function", obj.public_name)]
    return new_node


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
