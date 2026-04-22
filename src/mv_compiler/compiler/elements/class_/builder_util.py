import ast

from .symbol_table.method_info import MethodInfo
from .ast_util import *
from ..signature import create_signature_check_condition
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
        condition = create_signature_check_condition(method_info.parameters)

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
