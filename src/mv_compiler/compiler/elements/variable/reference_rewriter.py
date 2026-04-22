import ast


class VersionedValueNameRewriter(ast.NodeTransformer):
    """版付き変数の参照を、その定義版に固定したproxy参照へ差し替える。"""

    def __init__(self, variable_names: set[str], version: int):
        self.variable_names = variable_names
        self.version = version

    def visit_Name(self, node: ast.Name) -> ast.AST:
        if isinstance(node.ctx, ast.Load) and node.id in self.variable_names:
            return ast.Call(
                func=ast.Attribute(
                    value=ast.Name(id=node.id, ctx=ast.Load()),
                    attr="switch_to",
                    ctx=ast.Load(),
                ),
                args=[ast.Constant(value=self.version)],
                keywords=[],
            )
        return node
