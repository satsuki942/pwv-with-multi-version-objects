import ast
import copy

from ..symbol_table.symbol_table import SymbolTable
from ..symbol_table.method_info import MethodInfo

from ..ast_util import *
from ..dispatch import create_slow_path_dispatcher
from ...signature import create_signature_bind_check_call
from ....common.util.constants import (
    DEFAULT_VERSION_SELECTION_STRATEGY,
    INITIALIZE_METHOD_NAME,
    VERSION_SELECTION_LATEST,
    WRAPPER_SELF_ARG_NAME,
)

def build_stub_methods(
    symbol_table: SymbolTable,
    base_name: str,
    version_selection_strategy: str = DEFAULT_VERSION_SELECTION_STRATEGY,
) -> list[ast.FunctionDef]:
    """公開スタブメソッドを生成して返す。"""
    class_info = symbol_table.lookup_class(base_name)
    if not class_info:
        return []

    stubs: list[ast.FunctionDef] = []
    for method_name, overloads in class_info.methods.items():
        if method_name == INITIALIZE_METHOD_NAME:
            continue
    
        if class_info.has_consistent_signature(method_name):
            # A. シグネチャが一致する場合 -> 完全一致のスタブを生成
            stub = _generate_consistent_signature_stub(
                symbol_table,
                base_name,
                method_name,
                overloads,
                version_selection_strategy,
            )
        else:
            # B. シグネチャが不一致の場合 -> *args/**kwargs の汎用スタブを生成
            stub = _generate_inconsistent_signature_stub(
                symbol_table,
                base_name,
                method_name,
                overloads,
                version_selection_strategy,
            )
        
        if stub:
            stubs.append(stub)

    return stubs


# --- HELPER METHODS ---
def _generate_consistent_signature_stub(
    symbol_table: SymbolTable,
    base_name: str,
    method_name: str,
    overloads: list[MethodInfo],
    version_selection_strategy: str,
) -> ast.FunctionDef | None:
    """
    シグネチャが一致するスタブを生成する。
    """
    method_info = overloads[0]
    if not method_info.ast_node:
        return None

    # 1. メソッドシグネチャを再構成
    stub_args = copy.deepcopy(method_info.ast_node.args)
    _set_public_receiver_name(stub_args)
    
    stub_method = ast.FunctionDef(
        name=method_name,
        args=stub_args,
        body=[], decorator_list=[]
    )

    # 1.5
    if version_selection_strategy == VERSION_SELECTION_LATEST:
        # self.current_state.version_num
        current_version_num_ast = ast.Attribute(value=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_current_state_field_name(base_name), ctx=ast.Load()), 
                                            attr='_version_number',
                                            ctx=ast.Load())
        
        class_info = symbol_table.lookup_class(base_name)
        overloads = class_info.methods.get(method_name, [])
        latest_version_num = sorted([int(info.version) for info in overloads])[-1]
        latest_version_num_ast = ast.Constant(value=latest_version_num)

        ast_if = ast.If(
                test=ast.Compare(
                    left=current_version_num_ast,
                    ops=[ast.NotEq()],
                    comparators=[latest_version_num_ast],
                ),
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_switch_to_version_method_name(base_name), ctx=ast.Load()),
                            args=[latest_version_num_ast],
                            keywords=[],
                        )
                    )
                ],
                orelse=[],
            )
        
        stub_method.body.append(ast_if)

    # 2. fast path の AST（try ブロック）を生成
    call_args = []
    call_keywords = [
        ast.keyword(arg=WRAPPER_SELF_ARG_NAME, value=ast.Name(id='self', ctx=ast.Load()))
    ]

    for param in method_info.parameters:
        if param.kind in ('POSITIONAL_ONLY', 'POSITIONAL_OR_KEYWORD'):
            call_args.append(ast.Name(id=param.name, ctx=ast.Load()))
        elif param.kind == 'KEYWORD_ONLY':
            call_keywords.append(ast.keyword(arg=param.name, value=ast.Name(id=param.name, ctx=ast.Load())))
        elif param.kind == 'VAR_POSITIONAL':
            call_args.append(ast.Starred(value=ast.Name(id=param.name, ctx=ast.Load()), ctx=ast.Load()))
        elif param.kind == 'VAR_KEYWORD':
            call_keywords.append(ast.keyword(arg=None, value=ast.Name(id=param.name, ctx=ast.Load())))
    
    fast_path_call = ast.Call(
        func=ast.Attribute(value=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_current_state_field_name(base_name), ctx=ast.Load()), attr=method_name, ctx=ast.Load()),
        args=call_args,
        keywords=call_keywords
    )
    fast_path_body = [ast.Return(value=fast_path_call)]
    
    # 3. slow path の AST（except ブロック）を生成
    # このメソッドを持つ全バージョンを取得
    class_info = symbol_table.lookup_class(base_name)
    overloads = class_info.methods.get(method_name, [])
    callable_versions = sorted([int(info.version) for info in overloads])

    # current state に対象メソッドがない場合は、最新側の候補へ切り替える。
    if callable_versions:
        next_version_to_try = callable_versions[-1]
    else:
        return None

    slow_path_body = [
        # a. self._switch_to_version(<next_version_to_try>)
        ast.Expr(value=ast.Call(
            func=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_switch_to_version_method_name(base_name), ctx=ast.Load()),
            args=[ast.Constant(value=next_version_to_try)],
            keywords=[]
        )),
        
        # b. return self._xxx_current_state.method_name(...)
        ast.Return(value=fast_path_call)
    ]

    except_handler = ast.ExceptHandler(type=ast.Name(id='AttributeError', ctx=ast.Load()), name=None, body=slow_path_body)
    
    stub_method.body.append(ast.Try(body=fast_path_body, handlers=[except_handler], orelse=[], finalbody=[]))
    return stub_method


def _set_public_receiver_name(args: ast.arguments) -> None:
    if args.posonlyargs:
        args.posonlyargs[0] = ast.arg(arg='self')
    elif args.args:
        args.args[0] = ast.arg(arg='self')

def _generate_inconsistent_signature_stub(
    symbol_table: SymbolTable,
    base_name: str,
    method_name: str,
    overloads: list[MethodInfo],
    version_selection_strategy: str,
) -> ast.FunctionDef:
    """
    *args と **kwargs の汎用スタブを生成する。
    """
    # 1. スタブの骨格: def method_name(self, *args, **kwargs)
    stub_method = ast.FunctionDef(
        name=method_name,
        args=ast.arguments(
            posonlyargs=[], args=[ast.arg(arg='self')],
            vararg=ast.arg(arg='args'), kwarg=ast.arg(arg='kwargs'),
            kwonlyargs=[], kw_defaults=[], defaults=[]
        ),
        body=[], decorator_list=[]
    )

    # 1.5
    if version_selection_strategy == VERSION_SELECTION_LATEST:
        # self.current_state.version_num
        current_version_num_ast = ast.Attribute(value=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_current_state_field_name(base_name), ctx=ast.Load()), 
                                            attr='_version_number',
                                            ctx=ast.Load())
        
        class_info = symbol_table.lookup_class(base_name)
        overloads = class_info.methods.get(method_name, [])
        latest_version_num = sorted([int(info.version) for info in overloads])[-1]
        latest_version_num_ast = ast.Constant(value=latest_version_num)

        ast_if = ast.If(
                test=ast.Compare(
                    left=current_version_num_ast,
                    ops=[ast.NotEq()],
                    comparators=[latest_version_num_ast],
                ),
                body=[
                    ast.Expr(
                        value=ast.Call(
                            func=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_switch_to_version_method_name(base_name), ctx=ast.Load()),
                            args=[latest_version_num_ast],
                            keywords=[],
                        )
                    )
                ],
                orelse=[],
            )
        
        stub_method.body.append(ast_if)

    current_method_name = "_mvo_current_method"
    current_method_lookup = ast.Attribute(
        value=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=get_current_state_field_name(base_name), ctx=ast.Load()),
        attr=method_name, ctx=ast.Load()
    )
    current_method_call = ast.Call(
        func=ast.Name(id=current_method_name, ctx=ast.Load()),
        args=[ast.Starred(value=ast.Name(id='args', ctx=ast.Load()), ctx=ast.Load())],
        keywords=[
            ast.keyword(arg=WRAPPER_SELF_ARG_NAME, value=ast.Name(id='self', ctx=ast.Load())),
            ast.keyword(arg=None, value=ast.Name(id='kwargs', ctx=ast.Load()))
        ]
    )

    # 2. current state に対象メソッドが存在するかだけを確認する。
    except_handler = ast.ExceptHandler(
        type=ast.Name(id='AttributeError', ctx=ast.Load()),
        name=None,
        body=create_slow_path_dispatcher(base_name, method_name, overloads)
    )

    bind_check = create_signature_bind_check_call(
        ast.Name(id=current_method_name, ctx=ast.Load()),
        ast.Dict(
            keys=[ast.Constant(value=WRAPPER_SELF_ARG_NAME)],
            values=[ast.Name(id='self', ctx=ast.Load())],
        ),
    )
    orelse_body = [
        ast.If(
            test=bind_check,
            body=[ast.Return(value=current_method_call)],
            orelse=[],
        ),
        *create_slow_path_dispatcher(base_name, method_name, overloads),
    ]

    stub_method.body.append(ast.Try(
        body=[
            ast.Assign(
                targets=[ast.Name(id=current_method_name, ctx=ast.Store())],
                value=current_method_lookup,
            )
        ],
        handlers=[except_handler],
        orelse=orelse_body,
        finalbody=[]
    ))

    return stub_method
