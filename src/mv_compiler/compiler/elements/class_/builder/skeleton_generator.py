import ast
import copy
from typing import List
from ..symbol_table.symbol_table import SymbolTable
from ..ast_util import *
from ..template_util import TemplateRenamer
from ..template_util import load_template_ast
from ....common.util import logger
from ....common.util.constants import SWITCH_COUNT_ATTR_NAME, WRAPPER_SELF_ARG_NAME

_SWITCH_TO_VERSION_TEMPLATE = "switch_to_version_template.py"

def build_skeleton(
    class_name: str,
    symbol_table: SymbolTable,
    sync_asts: List[ast.FunctionDef],
) -> ast.ClassDef | None:
    class_info = symbol_table.lookup_class(class_name)
    if not class_info:
        logger.error_log(f"Class '{class_name}' not found in symbol table.")
        return None

    target_class = _build_wrapper_class(class_info)
    impl_classes = _build_impl_classes(class_info, class_name)
    singleton_stmt = _build_singleton_instance_list_stmt(class_info)
    switch_method = _create_switch_to_version_method(class_name, sync_asts)

    # 暫定: _switch_count 属性を注入
    switch_count_attr = ast.Assign(
        targets=[ast.Name(id=SWITCH_COUNT_ATTR_NAME, ctx=ast.Store())],
        value=ast.Constant(value=0)
    )
    body_items = [switch_count_attr, *impl_classes, singleton_stmt]
    if switch_method:
        body_items.append(switch_method)
    target_class.body = body_items

    return target_class


# --- ヘルパー関数 ---
def _build_wrapper_class(class_info) -> ast.ClassDef:
    # 全バージョンから親実装クラスのユニーク集合を作る
    all_unique_base_impls = {}
    for parent_list in class_info.versioned_bases.values():
        for parent_base_name, parent_version in parent_list:
            if parent_version == UNVERSIONED_CLASS_TAG:
                all_unique_base_impls[parent_base_name] = ast.Name(id=parent_base_name, ctx=ast.Load())
            else:
                parent_impl_name = get_impl_class_name(parent_version)
                full_name = f"{parent_base_name}.{parent_impl_name}"
                all_unique_base_impls[full_name] = ast.Attribute(
                    value=ast.Name(id=parent_base_name, ctx=ast.Load()),
                    attr=parent_impl_name,
                    ctx=ast.Load()
                )

    # wrapperクラス定義を作成
    target_class = ast.ClassDef(
        name=class_info.class_name,
        bases=list(all_unique_base_impls.values()),
        keywords=[], body=[], decorator_list=[]
    )
    return target_class

def _build_impl_classes(class_info, class_name: str) -> list[ast.ClassDef]:
    impl_classes: list[ast.ClassDef] = []

    for version_str in sorted(class_info.get_all_versions(), key=int):
        # 各バージョンごとの親実装クラス一覧を作成
        impl_bases = []
        parent_list = class_info.versioned_bases.get(version_str, [])
        for parent_base_name, parent_version in parent_list:
            if parent_version == UNVERSIONED_CLASS_TAG:
                impl_bases.append(ast.Name(id=parent_base_name, ctx=ast.Load()))
            else:
                parent_impl_name = get_impl_class_name(parent_version)
                impl_bases.append(ast.Attribute(
                    value=ast.Name(id=parent_base_name, ctx=ast.Load()),
                    attr=parent_impl_name,
                    ctx=ast.Load()
                ))

        # 実装クラス定義を作成
        target_impl_class = ast.ClassDef(
            name=get_impl_class_name(version_str),
            bases=impl_bases if impl_bases else [ast.Name(id='object', ctx=ast.Load())],
            keywords=[], body=[], decorator_list=[]
        )

        # TopLevelMethodTransformer を作成
        parent_info_list = class_info.versioned_bases.get(version_str, [])
        parent_context = None
        if parent_info_list:
            # 簡易化のため先頭の親のみを考慮
            if len(parent_info_list) > 1:
                logger.warning_log(f"Multiple inheritance detected in class '{class_name}' version '{version_str}'.")
                logger.warning_log("Current implementation only considers the first parent for method transformation.")
                logger.warning_log("This may lead to inconsistent behavior compared to Python's method resolution order (MRO).")
            parent_base_name, parent_version = parent_info_list[0]
            if parent_version == UNVERSIONED_CLASS_TAG:
                parent_context = ('normal', parent_base_name)
            else:
                parent_context = ('mvo', (parent_base_name, parent_version))
        method_transformer = TopLevelMethodTransformer(class_name, parent_context)

        # 1. versionedクラスのメソッドをimplへ統合
        for method_info in class_info.get_methods_for_version(version_str):
            if method_info.ast_node:
                member_copy = copy.deepcopy(method_info.ast_node)
                
                transformed_method = method_transformer.visit(member_copy)
                target_impl_class.body.append(transformed_method)

        # 2. _version_number 属性を注入
        version_attr_stmt = ast.Assign(
            targets=[ast.Name(id='_version_number', ctx=ast.Store())],
            value=ast.Constant(value=int(version_str))
        )
        target_impl_class.body.insert(0, version_attr_stmt)

        # 3. デフォルトコンストラクタを注入
        default_ctor = ast.FunctionDef(
            name='__init__',
            args=ast.arguments(posonlyargs=[], args=[ast.arg(arg='self')], kwonlyargs=[], kw_defaults=[], defaults=[]),
            body=[ast.Pass()],
            decorator_list=[]
        )
        target_impl_class.body.append(default_ctor)

        impl_classes.append(target_impl_class)

    return impl_classes

def _build_singleton_instance_list_stmt(class_info) -> ast.Assign:
    impl_class_values = []
    impl_class_keys = []
    for version_str in sorted(class_info.get_all_versions(), key=int):
        impl_name = get_impl_class_name(version_str)
        impl_class_keys.append(ast.Constant(value=int(version_str)))
        impl_class_values.append(ast.Call(func=ast.Name(id=impl_name, ctx=ast.Load()), args=[], keywords=[]))

    singleton_list_stmt = ast.Assign(
        targets=[ast.Name(id=get_version_instances_singleton_name(class_info.class_name), ctx=ast.Store())],
        value=ast.Dict(keys=impl_class_keys, values=impl_class_values)
    )
    return singleton_list_stmt

def _create_switch_to_version_method(
    class_name: str,
    sync_asts: List[ast.FunctionDef],
) -> ast.FunctionDef | None:
    template_ast = load_template_ast(_SWITCH_TO_VERSION_TEMPLATE)
    if not template_ast or not template_ast.body:
        return None

    switch_method_node = template_ast.body[0]
    sync_dispatch_chain = _create_sync_dispatch_chain(sync_asts)
    TemplateRenamer(class_name, sync_dispatch_chain).visit(switch_method_node)
    return switch_method_node

def _create_sync_dispatch_chain(sync_asts: List[ast.FunctionDef]) -> ast.If | None:
    """sync関数呼び出し用の if-else 連鎖を生成する。"""
    # from_ver をキーに (to_ver, func_name) のリストを作る
    sync_map: dict[str, list[tuple[int, int]]] = {}
    for func_node in sync_asts:
        from_ver, to_ver = get_sync_function_version_info(func_node)
        if from_ver and to_ver:
            sync_map.setdefault(from_ver, []).append((to_ver, func_node.name))

    # 外側の if-else 連鎖を生成 (if current_version_num == ...:)
    outer_top_if = None
    outer_current_if = None
    for from_ver, to_calls in sync_map.items():
        # 内側の if-else 連鎖を生成 (if version_num == ...:)
        inner_top_if = None
        inner_current_if = None
        for to_ver, func_name in to_calls:
            inner_if_stmt = ast.If(
                test=ast.Compare(left=ast.Name(id='version_num', ctx=ast.Load()), ops=[ast.Eq()], comparators=[ast.Constant(value=int(to_ver))]),
                body=[ast.Expr(value=ast.Call(
                    func=ast.Attribute(value=ast.Name(id='self', ctx=ast.Load()), attr=func_name, ctx=ast.Load()),
                    args=[ast.Name(id='self', ctx=ast.Load())], keywords=[]
                ))],
                orelse=[]
            )
            if inner_top_if is None:
                inner_top_if = inner_if_stmt
                inner_current_if = inner_top_if
            else:
                inner_current_if.orelse = [inner_if_stmt]
                inner_current_if = inner_if_stmt
        
        # 外側の if を生成
        outer_if_stmt = ast.If(
            test=ast.Compare(left=ast.Name(id='current_version_num', ctx=ast.Load()), ops=[ast.Eq()], comparators=[ast.Constant(value=int(from_ver))]),
            body=[inner_top_if] if inner_top_if else [ast.Pass()],
            orelse=[]
        )
        if outer_top_if is None:
            outer_top_if = outer_if_stmt
            outer_current_if = outer_top_if
        else:
            outer_current_if.orelse = [outer_if_stmt]
            outer_current_if = outer_if_stmt
            
    return outer_top_if

class TopLevelMethodTransformer(ast.NodeTransformer):
    """
    versionedクラスのトップレベルメソッドASTを変換する。
    - _wrapper_self をシグネチャに追加
    - 先頭引数を wrapper に再束縛
    - super() 呼び出しを書き換え
    """
    def __init__(self, class_name: str, parent_context: tuple | None):
        self.class_name = class_name
        self.parent_context = parent_context
        self.is_in_top_level_method = False
        self.top_level_self_name = None

    def visit_FunctionDef(self, node: ast.FunctionDef) -> ast.FunctionDef:
        if self.is_in_top_level_method:
            self.generic_visit(node)
            return node

        if node.args.posonlyargs:
            self_arg = node.args.posonlyargs[0]
        elif node.args.args:
            self_arg = node.args.args[0]
        else:
            return node

        self.is_in_top_level_method = True
        self.top_level_self_name = self_arg.arg

        # 1. `_wrapper_self` をシグネチャに追加
        wrapper_self_arg = ast.arg(arg=WRAPPER_SELF_ARG_NAME)
        if not node.args.kwonlyargs: node.args.kwonlyargs = []
        if not node.args.kw_defaults: node.args.kw_defaults = []
        node.args.kwonlyargs.append(wrapper_self_arg)
        node.args.kw_defaults.append(ast.Constant(value=None))

        # 2. 条件付きの再束縛: `self = _wrapper_self`
        #    if _wrapper_self is not None:
        #        self = _wrapper_self
        conditional_rebind_stmt = ast.If(
            test=ast.Compare(
                left=ast.Name(id=WRAPPER_SELF_ARG_NAME, ctx=ast.Load()),
                ops=[ast.IsNot()],
                comparators=[ast.Constant(value=None)]
            ),
            body=[
                ast.Assign(
                    targets=[ast.Name(id=self.top_level_self_name, ctx=ast.Store())],
                    value=ast.Name(id=WRAPPER_SELF_ARG_NAME, ctx=ast.Load())
                )
            ],
            orelse=[]
        )

        # 3. メソッド本体を走査して super() を書き換える
        new_body = [conditional_rebind_stmt]
        for statement in node.body:
            new_body.append(self.visit(statement))
        node.body = new_body
        
        # 4. 状態をリセット
        self.is_in_top_level_method = False
        self.top_level_self_name = None
        
        return node

    def visit_ClassDef(self, node: ast.ClassDef):
        # ネストされたクラスは走査しない（内側は別の継承/ self を持つため）
        return node
    
    def visit_Call(self, node: ast.Call) -> ast.Call:
        """
        - 書き換え: super() -> super(ClassName, _wrapper_self)
        """
        if self.is_in_top_level_method and isinstance(node.func, ast.Name) and node.func.id == 'super':
            if not self.parent_context:
                return node
            
            parent_type, parent_info = self.parent_context

            if not node.args: # super()
                if parent_type == 'normal':
                    node.args = [
                        ast.Name(id=self.class_name, ctx=ast.Load()),
                        ast.Name(id=WRAPPER_SELF_ARG_NAME, ctx=ast.Load())
                    ]
                
                elif parent_type == 'mvo':
                    parent_base_name, parent_version = parent_info
                    parent_impl_name = get_impl_class_name(parent_version)
                    
                    node.args = [
                        ast.Attribute(value=ast.Name(id=parent_base_name, ctx=ast.Load()), attr=parent_impl_name, ctx=ast.Load()),
                        ast.Name(id=WRAPPER_SELF_ARG_NAME, ctx=ast.Load())
                    ]
            elif len(node.args) == 2: # super(type, obj)
                logger.warning_log(f"super() with two arguments found in top-level method of versioned class '{self.class_name}'.")
                logger.warning_log("Current implementation only considers the first argument.")
        
        return self.generic_visit(node)
