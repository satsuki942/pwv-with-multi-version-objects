import ast

from .symbol_table.method_info import MethodInfo, ParameterInfo
from .ast_util import *
from ...common.util.constants import WRAPPER_SELF_ARG_NAME

def _create_slow_path_dispatcher(class_name: str, method_name: str, overloads: list[MethodInfo]) -> list[ast.AST]:
    """
    スローパス用の静的 if-elif 連鎖を生成する。
    """

    sorted_overloads = sorted(overloads, key=lambda m: int(m.version))
    
    top_if_stmt = None
    current_if_stmt = None

    for method_info in sorted_overloads:
        # a. if 条件を作成
        condition = _create_signature_check_condition(method_info.parameters)

        # b. if ブロック本体を生成
        if_body = [
            # self._xxx_switch_to_version(...)
            ast.Expr(value=ast.Call(
                func=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_switch_to_version_method_name(class_name), ctx=ast.Load()),
                args=[ast.Constant(value=int(method_info.version))], keywords=[]
            )),
            # return self._xxx_current_state.method_name(...)
            ast.Return(value=ast.Call(
                func=ast.Attribute(
                    value=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_current_state_field_name(class_name), ctx=ast.Load()),
                    attr=method_name, ctx=ast.Load()
                ),
                args=[ast.Starred(value=ast.Name(id='args', ctx=ast.Load()), ctx=ast.Load())],
                keywords=[
                    ast.keyword(arg=WRAPPER_SELF_ARG_NAME, value=ast.Name(id='self', ctx=ast.Load())),
                    ast.keyword(arg=None, value=ast.Name(id='kwargs', ctx=ast.Load()))
                ]
            ))
        ]
        
        # c. if-else 連鎖を構成
        if_stmt = ast.If(test=condition, body=if_body, orelse=[])
        if top_if_stmt is None:
            top_if_stmt = if_stmt
            current_if_stmt = top_if_stmt
        else:
            current_if_stmt.orelse = [if_stmt]
            current_if_stmt = if_stmt
    
    # 最後の else: TypeError を送出
    if current_if_stmt:
        current_if_stmt.orelse = [ast.Raise(exc=ast.Call(
            func=ast.Name(id='TypeError', ctx=ast.Load()),
            args=[ast.Constant(value=f"No version of '{method_name}' matches the provided arguments.")],
            keywords=[]
        ), cause=None)]

    return [top_if_stmt] if top_if_stmt else []

def _create_signature_check_condition(params: list[ParameterInfo]) -> ast.AST:
    """
    実行時引数 (*args, **kwargs) がメソッドシグネチャに合致するかを
    静的に判定するための複合ブール式を生成する。
    """
    # --- 前提 ---
    # 対象のメソッドシグネチャに
    # 位置専用引数 (/), キーワード専用引数 (*),
    # 可変長引数 (*args, **kwargs) が含まれない前提。
    
    param_names = [p.name for p in params]
    num_params = len(param_names)
    required_param_indices = [i for i, p in enumerate(params) if not p.has_default_value]

    conditions = []

    # 条件1: 位置引数の数が総引数数を超えない
    # 例: len(args) <= 3
    conditions.append(ast.Compare(
        left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
        ops=[ast.LtE()],
        comparators=[ast.Constant(value=num_params)]
    ))

    # 条件2: すべてのキーワード引数が有効な名前である
    # 例: kwargs.keys() <= {'param1', 'param2', ...}
    conditions.append(ast.Compare(
        left=ast.Call(func=ast.Attribute(value=ast.Name(id='kwargs', ctx=ast.Load()), attr='keys', ctx=ast.Load()), args=[], keywords=[]),
        ops=[ast.LtE()],
        comparators=[ast.Set(elts=[ast.Constant(value=name) for name in param_names])]
    ))

    # 条件3: 位置引数とキーワード引数で同じパラメータを二重に束縛しない
    # 例: not (len(args) > 0 and 'param1' in kwargs)
    for i, name in enumerate(param_names):
        conditions.append(ast.UnaryOp(
            op=ast.Not(),
            operand=ast.BoolOp(op=ast.And(), values=[
                ast.Compare(
                    left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
                    ops=[ast.Gt()],
                    comparators=[ast.Constant(value=i)]
                ),
                ast.Compare(
                    left=ast.Constant(value=name),
                    ops=[ast.In()],
                    comparators=[ast.Name(id='kwargs', ctx=ast.Load())]
                )
            ])
        ))

    # 条件4: 必須パラメータがすべて満たされる
    # 例: (len(args) > 0 or 'param1' in kwargs)
    for i in required_param_indices:
        name = param_names[i]
        conditions.append(ast.BoolOp(op=ast.Or(), values=[
            ast.Compare(
                left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
                ops=[ast.Gt()],
                comparators=[ast.Constant(value=i)]
            ),
            ast.Compare(
                left=ast.Constant(value=name),
                ops=[ast.In()],
                comparators=[ast.Name(id='kwargs', ctx=ast.Load())]
            )
        ]))

    # 条件5（冗長だが安全）: 位置引数+キーワード引数の合計が総引数数を超えない
    # 例: len(args) + len(kwargs) <= 3
    conditions.append(ast.Compare(
        left=ast.BinOp(
            left=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='args', ctx=ast.Load())], keywords=[]),
            op=ast.Add(),
            right=ast.Call(func=ast.Name(id='len', ctx=ast.Load()), args=[ast.Name(id='kwargs', ctx=ast.Load())], keywords=[])
        ),
        ops=[ast.LtE()],
        comparators=[ast.Constant(value=num_params)]
    ))

    # 全条件を AND で結合
    return ast.BoolOp(op=ast.And(), values=conditions)
