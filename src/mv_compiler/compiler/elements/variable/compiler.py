import ast
import copy

from ...common.util.constants import VERSION_SELECTION_LATEST


_VERSIONED_VALUE_RUNTIME = """
class VersionedValue:
    def __init__(self, values, strategy='continuity', current_version_getter=None):
        object.__setattr__(self, '_values', {int(k): v for k, v in values.items()})
        object.__setattr__(self, '_strategy', strategy)
        object.__setattr__(self, '_current_version_getter', current_version_getter)
        object.__setattr__(self, '_current_version', min(self._values.keys()))
        object.__setattr__(self, '_forced_version', None)

    def _resolve_version(self, version=None):
        if version is not None:
            return int(version)
        if self._forced_version is not None:
            return self._forced_version
        if self._strategy == 'latest':
            return max(self._values.keys())
        if self._current_version_getter is not None:
            return int(self._current_version_getter())
        return self._current_version

    def _value(self, version=None):
        version = self._resolve_version(version)
        object.__setattr__(self, '_current_version', version)
        return self._values[version]

    def switch_to(self, version):
        object.__setattr__(self, '_forced_version', int(version))
        object.__setattr__(self, '_current_version', int(version))
        return self

    def get(self, version=None):
        return self._value(version)

    def set(self, new_value, version=None):
        self._values[self._resolve_version(version)] = new_value
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


def collect_versioned_value_names(exports: dict) -> set[str]:
    return {
        name for name, spec in exports.items()
        if spec.get("kind") == "variable" and spec.get("binding") == "versioned_value"
    }


def build_module_runtime(strategy: str, latest_version: int) -> list[ast.AST]:
    runtime_nodes = ast.parse(_VERSIONED_VALUE_RUNTIME).body
    current_version = latest_version if strategy == VERSION_SELECTION_LATEST else 1
    runtime_nodes.append(ast.Assign(
        targets=[ast.Name(id="_MVO_CURRENT_VERSION", ctx=ast.Store())],
        value=ast.Constant(value=current_version),
    ))
    runtime_nodes.append(ast.parse(
        "def _mvo_set_module_version(version):\n"
        "    global _MVO_CURRENT_VERSION\n"
        "    _MVO_CURRENT_VERSION = int(version)\n"
        "    return _MVO_CURRENT_VERSION\n"
    ).body[0])
    return runtime_nodes


def build_variable_export(
    export_name: str,
    spec: dict,
    top_level_by_version: dict[int, dict[str, ast.AST]],
    versions: list[int],
    latest_version: int,
    version_selection_strategy: str,
) -> ast.AST | None:
    binding = spec.get("binding", "plain")
    if binding == "versioned_reference":
        binding = "plain"

    if binding == "versioned_value":
        values: list[ast.keyword] = []
        for version in versions:
            source_name = spec.get("versions", {}).get(str(version), export_name)
            value_ast = _extract_assignment_value(top_level_by_version[version].get(source_name))
            if value_ast is not None:
                values.append(ast.keyword(arg=str(version), value=value_ast))
        return ast.Assign(
            targets=[ast.Name(id=export_name, ctx=ast.Store())],
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
                    ast.keyword(
                        arg="current_version_getter",
                        value=ast.Lambda(
                            args=ast.arguments(posonlyargs=[], args=[], kwonlyargs=[], kw_defaults=[], defaults=[]),
                            body=ast.Name(id="_MVO_CURRENT_VERSION", ctx=ast.Load()),
                        ),
                    ),
                ],
            ),
        )

    source_name = spec.get("versions", {}).get(str(latest_version), export_name)
    node = copy.deepcopy(top_level_by_version[latest_version].get(source_name))
    if isinstance(node, ast.Assign):
        node.targets = [ast.Name(id=export_name, ctx=ast.Store())]
        return node
    if isinstance(node, ast.AnnAssign):
        node.target = ast.Name(id=export_name, ctx=ast.Store())
        return node
    return None


def _extract_assignment_value(node: ast.AST | None) -> ast.AST | None:
    if isinstance(node, ast.Assign):
        return copy.deepcopy(node.value)
    if isinstance(node, ast.AnnAssign):
        return copy.deepcopy(node.value)
    return None
