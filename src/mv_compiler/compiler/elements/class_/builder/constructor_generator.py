import ast

from ..symbol_table.symbol_table import SymbolTable
from ..ast_util import *
from ..template_util import load_template_ast, TemplateRenamer
from ..dispatch import create_slow_path_dispatcher
from ....common.util import logger
from ....common.util.constants import INITIALIZE_METHOD_NAME

_CONSTRUCTOR_TEMPLATE = "constructor_template.py"

def build_constructor(symbol_table: SymbolTable, class_name: str) -> ast.FunctionDef | None:
    """統合クラス用の __init__ を生成して返す。"""
    template_ast = _load_constructor_template_ast()
    if not template_ast:
        return None

    # 0. テンプレートのプレースホルダを置換
    TemplateRenamer(class_name=class_name).visit(template_ast)

    # 1. __initialize__ の情報をシンボルテーブルから取得
    class_info = symbol_table.lookup_class(class_name)
    initialize_overloads = class_info.methods.get(INITIALIZE_METHOD_NAME, [])

    # 2. スローパスのディスパッチ（if-elif）生成
    slow_path_body = create_slow_path_dispatcher(
        class_name, INITIALIZE_METHOD_NAME, initialize_overloads
    )
    if not slow_path_body:
        slow_path_body.append(ast.Pass())

    # 3. exceptブロックを生成したスローパスで置換
    try_except_node = template_ast.body[1]  # Node: try-except
    except_handler = try_except_node.handlers[0] # Node: except
    except_handler.body = slow_path_body # except block body replacement

    return template_ast

def _load_constructor_template_ast() -> ast.FunctionDef | None:
    template_ast = load_template_ast(_CONSTRUCTOR_TEMPLATE)
    for node in ast.walk(template_ast):
        if isinstance(node, ast.FunctionDef) and node.name == '__init__':
            return node
    logger.error_log("constructorテンプレートに __init__ が見つかりません。")
    return None
