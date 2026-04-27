import ast
import copy

from ..entity import entity_source_node


_VERSIONED_VALUE_RUNTIME = """
class VersionedValue:
    def __init__(self, values, strategy='continuity'):
        object.__setattr__(self, '_values', {int(k): v for k, v in values.items()})
        object.__setattr__(self, '_strategy', strategy)
        current_version = max(self._values.keys())
        object.__setattr__(self, '_current_version', current_version)

    def _resolve_version(self):
        return self._current_version

    def _value(self):
        return self._values[self._resolve_version()]

    def get(self):
        return self._value()

    def set(self, new_value):
        self._values[self._resolve_version()] = new_value
        return new_value

    def __getattr__(self, name):
        return getattr(self._value(), name)

    def __setattr__(self, name, value):
        if name.startswith('_'):
            object.__setattr__(self, name, value)
        else:
            setattr(self._value(), name, value)

    def __getitem__(self, key):
        return self._value()[key]

    def __setitem__(self, key, value):
        self._value()[key] = value

    def __call__(self, *args, **kwargs):
        return self._value()(*args, **kwargs)

    def __bool__(self):
        return bool(self._value())

    def __str__(self):
        return str(self._value())

    def __repr__(self):
        return repr(self._value())

    def __add__(self, other):
        return self._value() + other

    def __radd__(self, other):
        return other + self._value()

    def __sub__(self, other):
        return self._value() - other

    def __rsub__(self, other):
        return other - self._value()

    def __mul__(self, other):
        return self._value() * other

    def __rmul__(self, other):
        return other * self._value()

    def __truediv__(self, other):
        return self._value() / other

    def __rtruediv__(self, other):
        return other / self._value()
"""


def build_module_runtime(strategy: str, latest_version: int) -> list[ast.AST]:
    """変数versioning用の実行時proxyクラス定義ASTを生成する。

    Args:
        strategy: 実行時にversionを選ぶ戦略名。
        latest_version: 当該モジュールで最新のversion番号。

    Returns:
        生成モジュールへ追加するランタイム定義ASTのリスト。
    """
    return ast.parse(_VERSIONED_VALUE_RUNTIME).body


def build_variable_entity(
    entity_name: str,
    spec: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    latest_version: int,
    version_selection_strategy: str,
) -> ast.AST | None:
    """variable entityを、versioned_by設定に応じた生成ASTへ変換する。

    Args:
        entity_name: 生成後に束縛される論理変数名。
        spec: 正規化済みentity spec。
        top_level_by_version: versionごとのトップレベル定義索引。
        versions: 当該モジュールで宣言されているversion一覧。
        latest_version: 当該モジュールで最新のversion番号。
        version_selection_strategy: 実行時にversionを選ぶ戦略名。

    Returns:
        generatedならVersionedValue代入AST、referencedならlatest右辺の代表束縛AST。
        対応する代入ノードが見つからない場合はNone。
    """
    versioned_by = spec.get("versioned_by")
    if versioned_by == "generated":
        # compiler側でVersionedValueを作り、各versionの右辺値をproxyに保持させる。
        values: list[ast.keyword] = []
        for version in versions:
            value_ast = _extract_assignment_value(entity_source_node(top_level_by_version, entity_name, spec, version))
            if value_ast is not None:
                values.append(ast.keyword(arg=str(version), value=value_ast))
        return ast.Assign(
            targets=[ast.Name(id=entity_name, ctx=ast.Store())],
            value=ast.Call(
                func=ast.Name(id="VersionedValue", ctx=ast.Load()),
                args=[
                    ast.Dict(
                        keys=[ast.Constant(value=int(keyword.arg)) for keyword in values],
                        values=[keyword.value for keyword in values],
                    )
                ],
                keywords=[
                    ast.keyword(arg="strategy", value=ast.Constant(value=version_selection_strategy)),
                ],
            ),
        )

    # referencedは参照先が既にversionedである前提なので、latest側の右辺を代表束縛にする。
    node = copy.deepcopy(entity_source_node(top_level_by_version, entity_name, spec, latest_version))
    if isinstance(node, ast.Assign):
        node.targets = [ast.Name(id=entity_name, ctx=ast.Store())]
        return node
    if isinstance(node, ast.AnnAssign):
        node.target = ast.Name(id=entity_name, ctx=ast.Store())
        return node
    return None


def _extract_assignment_value(node: ast.AST | None) -> ast.AST | None:
    """Assign/AnnAssignから、VersionedValueに保持させる右辺ASTだけを取り出す。"""
    if isinstance(node, ast.Assign):
        return copy.deepcopy(node.value)
    if isinstance(node, ast.AnnAssign):
        return copy.deepcopy(node.value)
    return None
